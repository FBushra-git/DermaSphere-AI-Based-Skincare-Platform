from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import (
    Category,
    Ingredient,
    Inventory,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
    Role,
    SellerProfile,
    SkinConcern,
    SkinType,
    User,
    product_ingredients,
    product_skin_concerns,
    product_skin_types,
)
from app.schemas import InventoryUpdate, OrderStatusUpdate, ProductRead, ProductUpdate

router = APIRouter(prefix="/api/seller", tags=["seller workspace"])


def get_seller(db: Session, user: User) -> SellerProfile:
    seller = db.scalar(select(SellerProfile).where(SellerProfile.user_id == user.id))
    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")
    return seller


@router.get("/products")
def list_my_products(
    db: Session = Depends(get_db), user: User = Depends(require_roles(Role.SELLER))
):
    seller = get_seller(db, user)
    rows = db.execute(
        select(Product, Inventory.available_quantity)
        .outerjoin(Inventory, Inventory.product_id == Product.id)
        .where(Product.seller_id == seller.id)
        .order_by(Product.created_at.desc())
    ).all()
    product_ids = [product.id for product, _ in rows]
    associations = {
        "ingredient_ids": (product_ingredients, product_ingredients.c.ingredient_id),
        "skin_type_ids": (product_skin_types, product_skin_types.c.skin_type_id),
        "skin_concern_ids": (
            product_skin_concerns,
            product_skin_concerns.c.skin_concern_id,
        ),
    }
    related: dict[str, dict[str, list[str]]] = {
        product_id: {key: [] for key in associations} for product_id in product_ids
    }
    for key, (table, value_column) in associations.items():
        if product_ids:
            relation_rows = db.execute(
                select(table.c.product_id, value_column).where(
                    table.c.product_id.in_(product_ids)
                )
            )
            for product_id, related_id in relation_rows:
                related[product_id][key].append(related_id)
    return [
        {
            **ProductRead.model_validate(product).model_dump(mode="json"),
            "available_quantity": quantity or 0,
            **related[product.id],
        }
        for product, quantity in rows
    ]


@router.patch("/products/{product_id}", response_model=ProductRead)
def update_my_product(
    product_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SELLER)),
):
    seller = get_seller(db, user)
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.seller_id == seller.id)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in your store")
    changes = payload.model_dump(exclude_unset=True)
    if product.status == ProductStatus.ARCHIVED:
        raise HTTPException(
            status_code=409, detail="Archived products cannot be edited"
        )
    if payload.category_id and not db.get(Category, payload.category_id):
        raise HTTPException(status_code=422, detail="Category does not exist")
    relationship_fields = {
        "ingredient_ids": (product_ingredients, Ingredient, "ingredient_id"),
        "skin_type_ids": (product_skin_types, SkinType, "skin_type_id"),
        "skin_concern_ids": (product_skin_concerns, SkinConcern, "skin_concern_id"),
    }
    for field, value in changes.items():
        if field in relationship_fields or field in {
            "ingredient_ids",
            "skin_type_ids",
            "skin_concern_ids",
        }:
            continue
        setattr(product, field, str(value) if field == "image_url" and value else value)
    for field, (table, model, relation_column) in relationship_fields.items():
        if field in changes:
            related_ids = list(dict.fromkeys(changes[field] or []))
            valid_ids = (
                set(db.scalars(select(model.id).where(model.id.in_(related_ids))).all())
                if related_ids
                else set()
            )
            if valid_ids != set(related_ids):
                raise HTTPException(
                    status_code=422,
                    detail=f"One or more {model.__tablename__} records do not exist",
                )
            db.execute(table.delete().where(table.c.product_id == product.id))
            if related_ids:
                db.execute(
                    table.insert(),
                    [
                        {"product_id": product.id, relation_column: related_id}
                        for related_id in related_ids
                    ],
                )
    if changes and product.status in {ProductStatus.APPROVED, ProductStatus.REJECTED}:
        product.status = ProductStatus.PENDING
    db.commit()
    db.refresh(product)
    return product


@router.put("/products/{product_id}/inventory")
def update_inventory(
    product_id: str,
    payload: InventoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SELLER)),
):
    seller = get_seller(db, user)
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.seller_id == seller.id)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in your store")
    inventory = db.get(Inventory, product.id)
    if not inventory:
        inventory = Inventory(
            product_id=product.id,
            available_quantity=payload.available_quantity,
            sold_quantity=0,
        )
        db.add(inventory)
    else:
        inventory.available_quantity = payload.available_quantity
    db.commit()
    return {
        "product_id": product.id,
        "available_quantity": inventory.available_quantity,
        "sold_quantity": inventory.sold_quantity,
    }


@router.get("/orders")
def list_my_orders(
    db: Session = Depends(get_db), user: User = Depends(require_roles(Role.SELLER))
):
    seller = get_seller(db, user)
    rows = db.execute(
        select(Order, OrderItem)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(OrderItem.seller_id == seller.id)
        .order_by(Order.created_at.desc())
    ).all()
    seller_sets: dict[str, set[str]] = {}
    for order, _ in rows:
        if order.id not in seller_sets:
            seller_sets[order.id] = set(
                db.scalars(
                    select(OrderItem.seller_id).where(OrderItem.order_id == order.id)
                ).all()
            )
    return [
        {
            "order_id": order.id,
            "status": order.status,
            "created_at": order.created_at,
            "product_id": item.product_id,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "line_total": item.unit_price * item.quantity,
            "can_manage_order": seller_sets[order.id] == {seller.id},
        }
        for order, item in rows
    ]


@router.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SELLER)),
):
    seller = get_seller(db, user)
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).all()
    if not items or any(item.seller_id != seller.id for item in items):
        raise HTTPException(
            status_code=403,
            detail="You cannot update an order containing another seller's products",
        )
    allowed = {
        OrderStatus.PENDING: {OrderStatus.CONFIRMED},
        OrderStatus.CONFIRMED: {OrderStatus.PROCESSING},
        OrderStatus.PROCESSING: {OrderStatus.SHIPPED},
        OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    }
    next_status = OrderStatus(payload.status)
    if next_status not in allowed.get(order.status, set()):
        raise HTTPException(status_code=409, detail="Invalid order status transition")
    order.status = next_status
    db.commit()
    return {"order_id": order.id, "status": order.status}


@router.get("/reports/sales")
def seller_sales(
    db: Session = Depends(get_db), user: User = Depends(require_roles(Role.SELLER))
):
    seller = get_seller(db, user)
    total = db.scalar(
        select(func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.seller_id == seller.id, Order.status != OrderStatus.CANCELLED)
    ) or Decimal("0.00")
    order_count = (
        db.scalar(
            select(func.count(func.distinct(OrderItem.order_id))).where(
                OrderItem.seller_id == seller.id
            )
        )
        or 0
    )
    product_count = (
        db.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.seller_id == seller.id)
        )
        or 0
    )
    return {"total_sales": total, "orders": order_count, "products": product_count}
