from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import (
    Ingredient,
    Inventory,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductApproval,
    ProductStatus,
    Review,
    Role,
    SellerProfile,
    User,
)
from app.schemas import (
    AccountStatusUpdate,
    AdminOrderStatusUpdate,
    IngredientUpdate,
    ProductDecision,
    ProductRead,
    ReviewModeration,
)

router = APIRouter(prefix="/api/admin", tags=["administration"])


@router.get("/products/pending")
def pending_products(
    db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))
):
    rows = db.scalars(
        select(Product)
        .where(Product.status == ProductStatus.PENDING)
        .order_by(Product.created_at)
    ).all()
    return [ProductRead.model_validate(product) for product in rows]


def decide(
    product_id: str,
    status: ProductStatus,
    comment: str | None,
    admin: User,
    db: Session,
) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.status != ProductStatus.PENDING:
        raise HTTPException(
            status_code=409, detail="Only pending products can be reviewed"
        )
    product.status = status
    db.add(
        ProductApproval(
            product_id=product.id,
            admin_id=admin.id,
            status=status.value,
            comment=comment,
            decided_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.refresh(product)
    return product


@router.patch("/products/{product_id}/approve", response_model=ProductRead)
def approve_product(
    product_id: str,
    payload: ProductDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    return decide(product_id, ProductStatus.APPROVED, payload.comment, admin, db)


@router.patch("/products/{product_id}/reject", response_model=ProductRead)
def reject_product(
    product_id: str,
    payload: ProductDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    return decide(product_id, ProductStatus.REJECTED, payload.comment, admin, db)


@router.get("/overview")
def overview(
    db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))
):

    from app.models import Order, SellerProfile

    def count(model, *criteria):
        return db.scalar(select(func.count()).select_from(model).where(*criteria)) or 0

    return {
        "users": count(User),
        "sellers": count(SellerProfile),
        "products": count(Product),
        "pending_products": count(Product, Product.status == ProductStatus.PENDING),
        "approved_products": count(Product, Product.status == ProductStatus.APPROVED),
        "orders": count(Order),
    }


@router.get("/inventory/low-stock")
def low_stock(
    threshold: int = 5,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    rows = db.execute(
        select(Inventory, Product.name)
        .join(Product)
        .where(Inventory.available_quantity <= threshold)
        .order_by(Inventory.available_quantity)
    ).all()
    return [
        {
            "product_id": inventory.product_id,
            "name": name,
            "available_quantity": inventory.available_quantity,
            "sold_quantity": inventory.sold_quantity,
        }
        for inventory, name in rows
    ]


@router.get("/users")
def list_users(
    q: str | None = None,
    role: Role | None = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    from sqlalchemy import or_

    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(status_code=422, detail="Invalid pagination values")
    statement = select(User)
    if role:
        statement = statement.where(User.role == role)
    if q:
        search = f"%{q.strip()}%"
        statement = statement.where(
            or_(User.name.ilike(search), User.email.ilike(search))
        )
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    records = db.scalars(
        statement.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "email": item.email,
                "role": item.role,
                "phone": item.phone,
                "is_active": item.is_active,
                "created_at": item.created_at,
            }
            for item in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: str,
    payload: AccountStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and not payload.is_active:
        raise HTTPException(
            status_code=409, detail="You cannot deactivate your own account"
        )
    target.is_active = payload.is_active
    db.commit()
    return {"id": target.id, "is_active": target.is_active}


@router.get("/sellers")
def list_sellers(
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    statement = select(SellerProfile, User).join(User, User.id == SellerProfile.user_id)
    if q:
        search = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                SellerProfile.store_name.ilike(search),
                User.name.ilike(search),
                User.email.ilike(search),
            )
        )
    rows = db.execute(statement.order_by(SellerProfile.created_at.desc())).all()
    return [
        {
            "id": seller.id,
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "store_name": seller.store_name,
            "description": seller.description,
            "verification_status": seller.verification_status,
            "is_active": user.is_active,
        }
        for seller, user in rows
    ]


@router.patch("/products/{product_id}/archive")
def archive_product(
    product_id: str,
    payload: ProductDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.status = ProductStatus.ARCHIVED
    db.add(
        ProductApproval(
            product_id=product.id,
            admin_id=admin.id,
            status=ProductStatus.ARCHIVED.value,
            comment=payload.comment,
            decided_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return {"id": product.id, "status": product.status}


@router.get("/orders")
def list_all_orders(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    rows = db.execute(
        select(Order, User.name, User.email)
        .join(User, User.id == Order.user_id)
        .order_by(Order.created_at.desc())
        .limit(500)
    ).all()
    return [
        {
            "id": order.id,
            "customer_name": name,
            "customer_email": email,
            "total_amount": order.total_amount,
            "shipping_address": order.shipping_address,
            "status": order.status,
            "created_at": order.created_at,
        }
        for order, name, email in rows
    ]


@router.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: str,
    payload: AdminOrderStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    requested_status = OrderStatus(payload.status)
    if (
        order.status == OrderStatus.CANCELLED
        and requested_status != OrderStatus.CANCELLED
    ):
        raise HTTPException(
            status_code=409, detail="Cancelled orders cannot be reopened"
        )
    if (
        requested_status == OrderStatus.CANCELLED
        and order.status != OrderStatus.CANCELLED
    ):
        items = db.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        for item in items:
            inventory = db.scalar(
                select(Inventory)
                .where(Inventory.product_id == item.product_id)
                .with_for_update()
            )
            if inventory:
                inventory.available_quantity += item.quantity
                inventory.sold_quantity = max(
                    0, inventory.sold_quantity - item.quantity
                )
    order.status = requested_status
    db.commit()
    return {"id": order.id, "status": order.status}


@router.get("/reviews/reported")
def reported_reviews(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    rows = db.execute(
        select(Review, User.name, Product.name)
        .join(User, User.id == Review.user_id)
        .join(Product, Product.id == Review.product_id)
        .where(Review.is_reported.is_(True))
        .order_by(Review.created_at.desc())
    ).all()
    return [
        {
            "id": review.id,
            "customer_name": customer_name,
            "product_name": product_name,
            "rating": review.rating,
            "body": review.body,
            "created_at": review.created_at,
        }
        for review, customer_name, product_name in rows
    ]


@router.patch("/reviews/{review_id}/report")
def resolve_review_report(
    review_id: str,
    payload: ReviewModeration,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.is_reported = payload.is_reported
    db.commit()
    return {"id": review.id, "is_reported": review.is_reported}


@router.delete("/reviews/{review_id}", status_code=204)
def delete_review(
    review_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    db.commit()


@router.patch("/ingredients/{ingredient_id}")
def update_ingredient(
    ingredient_id: str,
    payload: IngredientUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    ingredient = db.get(Ingredient, ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(
            ingredient, field, value.strip() if field == "name" and value else value
        )
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.delete("/ingredients/{ingredient_id}", status_code=204)
def delete_ingredient(
    ingredient_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    from sqlalchemy.exc import IntegrityError

    ingredient = db.get(Ingredient, ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    db.delete(ingredient)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Ingredient is still used by a product"
        ) from exc
