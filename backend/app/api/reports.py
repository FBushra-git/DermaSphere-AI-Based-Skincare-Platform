from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import (
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
    UserSkinProfile,
    profile_skin_concerns,
)

router = APIRouter(prefix="/api/admin/reports", tags=["administrative reports"])


@router.get("/overview")
def overview(
    db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))
):
    def count(model, *criteria):
        return db.scalar(select(func.count()).select_from(model).where(*criteria)) or 0

    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)
    return {
        "total_users": count(User),
        "total_sellers": count(SellerProfile),
        "new_registrations_30d": count(User, User.created_at >= month_ago),
        "total_products": count(Product),
        "approved_products": count(Product, Product.status == ProductStatus.APPROVED),
        "pending_products": count(Product, Product.status == ProductStatus.PENDING),
        "rejected_products": count(Product, Product.status == ProductStatus.REJECTED),
        "total_orders": count(Order),
        "sales_total": db.scalar(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.status != OrderStatus.CANCELLED
            )
        )
        or Decimal("0.00"),
    }


@router.get("/sales")
def sales_report(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    totals = db.execute(
        select(
            func.date(Order.created_at).label("sale_date"),
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
        )
        .where(Order.created_at >= cutoff, Order.status != OrderStatus.CANCELLED)
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    ).all()
    by_seller = db.execute(
        select(
            SellerProfile.store_name,
            func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0),
        )
        .join(OrderItem, OrderItem.seller_id == SellerProfile.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status != OrderStatus.CANCELLED)
        .group_by(SellerProfile.id, SellerProfile.store_name)
        .order_by(func.sum(OrderItem.unit_price * OrderItem.quantity).desc())
    ).all()
    by_product = db.execute(
        select(
            OrderItem.product_id,
            OrderItem.product_name,
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.unit_price * OrderItem.quantity),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status != OrderStatus.CANCELLED)
        .group_by(OrderItem.product_id, OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(20)
    ).all()
    return {
        "daily": [
            {"date": str(row.sale_date), "orders": row[1], "sales": row[2]}
            for row in totals
        ],
        "by_seller": [{"seller": name, "sales": amount} for name, amount in by_seller],
        "top_products": [
            {"product_id": pid, "product": name, "units": units, "sales": total}
            for pid, name, units, total in by_product
        ],
    }


@router.get("/inventory")
def inventory_report(
    threshold: int = Query(default=5, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    rows = db.execute(
        select(Inventory, Product.name, Product.status)
        .join(Product, Product.id == Inventory.product_id)
        .where(Inventory.available_quantity <= threshold)
        .order_by(Inventory.available_quantity)
    ).all()
    return {
        "low_stock": [
            {
                "product_id": inventory.product_id,
                "name": name,
                "quantity": inventory.available_quantity,
                "status": "out_of_stock"
                if inventory.available_quantity == 0
                else "low_stock",
                "product_status": product_status,
            }
            for inventory, name, product_status in rows
        ]
    }


@router.get("/skin-trends")
def skin_trends(
    db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))
):
    type_rows = db.execute(
        select(SkinType.name, func.count(UserSkinProfile.id))
        .join(UserSkinProfile, UserSkinProfile.skin_type_id == SkinType.id)
        .group_by(SkinType.id, SkinType.name)
        .order_by(func.count(UserSkinProfile.id).desc())
    ).all()
    concern_rows = db.execute(
        select(SkinConcern.name, func.count(profile_skin_concerns.c.profile_id))
        .join(
            profile_skin_concerns,
            profile_skin_concerns.c.skin_concern_id == SkinConcern.id,
        )
        .group_by(SkinConcern.id, SkinConcern.name)
        .order_by(func.count(profile_skin_concerns.c.profile_id).desc())
    ).all()
    return {
        "skin_types": [
            {"name": name, "profiles": amount} for name, amount in type_rows
        ],
        "skin_concerns": [
            {"name": name, "profiles": amount} for name, amount in concern_rows
        ],
    }
