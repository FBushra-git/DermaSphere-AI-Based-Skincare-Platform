from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import Inventory, Product, ProductApproval, ProductStatus, Role, User
from app.schemas import ProductDecision, ProductRead

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
    from sqlalchemy import func

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
