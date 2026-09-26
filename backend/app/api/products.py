from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import (
    Category,
    Ingredient,
    Inventory,
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
from app.schemas import ProductCreate, ProductRead

router = APIRouter(prefix="/api/products", tags=["products"])


def product_query():
    return select(Product, Inventory.available_quantity).outerjoin(
        Inventory, Inventory.product_id == Product.id
    )


@router.get("")
def list_products(
    q: str | None = None,
    category_id: str | None = None,
    skin_type_id: str | None = None,
    skin_concern_id: str | None = None,
    ingredient_id: str | None = None,
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    in_stock: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = product_query().where(Product.status == ProductStatus.APPROVED)
    if q:
        search = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(search),
                Product.brand.ilike(search),
                Product.description.ilike(search),
                Product.id.in_(
                    select(product_ingredients.c.product_id)
                    .join(Ingredient)
                    .where(Ingredient.name.ilike(search))
                ),
            )
        )
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if skin_type_id:
        stmt = stmt.join(product_skin_types).where(
            product_skin_types.c.skin_type_id == skin_type_id
        )
    if skin_concern_id:
        stmt = stmt.join(product_skin_concerns).where(
            product_skin_concerns.c.skin_concern_id == skin_concern_id
        )
    if ingredient_id:
        stmt = stmt.join(product_ingredients).where(
            product_ingredients.c.ingredient_id == ingredient_id
        )
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if in_stock is True:
        stmt = stmt.where(Inventory.available_quantity > 0)
    elif in_stock is False:
        stmt = stmt.where(
            or_(Inventory.available_quantity == 0, Inventory.product_id.is_(None))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Product.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                **ProductRead.model_validate(product).model_dump(mode="json"),
                "available_quantity": quantity or 0,
            }
            for product, quantity in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{product_id}")
def product_detail(product_id: str, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product or product.status != ProductStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Product not found")
    ingredients = db.execute(
        select(
            Ingredient.id,
            Ingredient.name,
            Ingredient.description,
            Ingredient.benefits,
            Ingredient.cautions,
        )
        .join(product_ingredients)
        .where(product_ingredients.c.product_id == product_id)
    ).all()
    skin_types = db.scalars(
        select(SkinType.name)
        .join(product_skin_types)
        .where(product_skin_types.c.product_id == product_id)
    ).all()
    concerns = db.scalars(
        select(SkinConcern.name)
        .join(product_skin_concerns)
        .where(product_skin_concerns.c.product_id == product_id)
    ).all()
    inventory = db.get(Inventory, product_id)
    return {
        **ProductRead.model_validate(product).model_dump(mode="json"),
        "available_quantity": inventory.available_quantity if inventory else 0,
        "ingredients": [
            dict(
                id=i.id,
                name=i.name,
                description=i.description,
                benefits=i.benefits,
                cautions=i.cautions,
            )
            for i in ingredients
        ],
        "suitable_skin_types": skin_types,
        "suitable_concerns": concerns,
    }


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SELLER)),
):
    seller = db.scalar(select(SellerProfile).where(SellerProfile.user_id == user.id))
    if not seller:
        raise HTTPException(status_code=409, detail="Seller profile is not set up")
    if payload.category_id and not db.get(Category, payload.category_id):
        raise HTTPException(status_code=422, detail="Category does not exist")
    product = Product(
        seller_id=seller.id,
        category_id=payload.category_id,
        name=payload.name.strip(),
        brand=payload.brand.strip(),
        description=payload.description.strip(),
        price=payload.price,
        image_url=str(payload.image_url) if payload.image_url else None,
        benefits=payload.benefits,
        usage_instructions=payload.usage_instructions,
        cautions=payload.cautions,
        status=ProductStatus.PENDING,
    )
    db.add(product)
    db.flush()
    db.add(
        Inventory(
            product_id=product.id,
            available_quantity=payload.stock_quantity,
            sold_quantity=0,
        )
    )
    for table, ids, model, relation_column in [
        (product_ingredients, payload.ingredient_ids, Ingredient, "ingredient_id"),
        (product_skin_types, payload.skin_type_ids, SkinType, "skin_type_id"),
        (
            product_skin_concerns,
            payload.skin_concern_ids,
            SkinConcern,
            "skin_concern_id",
        ),
    ]:
        if ids:
            valid = set(db.scalars(select(model.id).where(model.id.in_(ids))).all())
            if valid != set(ids):
                raise HTTPException(
                    status_code=422,
                    detail=f"One or more {model.__tablename__} records do not exist",
                )
            db.execute(
                table.insert(),
                [
                    {"product_id": product.id, relation_column: item_id}
                    for item_id in ids
                ],
            )
    db.commit()
    db.refresh(product)
    return product
