from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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
    SkinConcern,
    SkinType,
    User,
    product_ingredients,
)
from app.schemas import IngredientCreate, NamedRecord

router = APIRouter(tags=["catalog"])


@router.get("/api/categories")
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
    ).all()


@router.get("/api/skin-types")
def list_skin_types(db: Session = Depends(get_db)):
    return db.scalars(select(SkinType).order_by(SkinType.name)).all()


@router.get("/api/skin-concerns")
def list_skin_concerns(db: Session = Depends(get_db)):
    return db.scalars(select(SkinConcern).order_by(SkinConcern.name)).all()


@router.get("/api/ingredients")
def list_ingredients(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Ingredient).order_by(Ingredient.name)
    if q:
        stmt = stmt.where(Ingredient.name.ilike(f"%{q.strip()}%"))
    return db.scalars(stmt.limit(100)).all()


@router.get("/api/ingredients/{ingredient_id}")
def ingredient_detail(ingredient_id: str, db: Session = Depends(get_db)):
    ingredient = db.get(Ingredient, ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    products = db.execute(
        select(Product, Inventory.available_quantity)
        .join(product_ingredients, product_ingredients.c.product_id == Product.id)
        .outerjoin(Inventory, Inventory.product_id == Product.id)
        .where(
            product_ingredients.c.ingredient_id == ingredient.id,
            Product.status == ProductStatus.APPROVED,
        )
        .order_by(Product.name)
    ).all()
    return {
        "id": ingredient.id,
        "name": ingredient.name,
        "description": ingredient.description,
        "common_uses": ingredient.common_uses,
        "benefits": ingredient.benefits,
        "cautions": ingredient.cautions,
        "products": [
            {
                "id": product.id,
                "name": product.name,
                "brand": product.brand,
                "price": product.price,
                "image_url": product.image_url,
                "available_quantity": quantity or 0,
            }
            for product, quantity in products
        ],
    }


@router.post("/api/admin/categories", status_code=201)
def create_category(
    payload: NamedRecord,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    if db.scalar(select(Category).where(Category.name.ilike(payload.name.strip()))):
        raise HTTPException(status_code=409, detail="Category already exists")
    item = Category(name=payload.name.strip(), description=payload.description)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/api/admin/skin-types", status_code=201)
def create_skin_type(
    payload: NamedRecord,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    if db.scalar(select(SkinType).where(SkinType.name.ilike(payload.name.strip()))):
        raise HTTPException(status_code=409, detail="Skin type already exists")
    item = SkinType(name=payload.name.strip(), description=payload.description)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/api/admin/skin-concerns", status_code=201)
def create_skin_concern(
    payload: NamedRecord,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    if db.scalar(
        select(SkinConcern).where(SkinConcern.name.ilike(payload.name.strip()))
    ):
        raise HTTPException(status_code=409, detail="Skin concern already exists")
    item = SkinConcern(name=payload.name.strip(), description=payload.description)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/api/admin/ingredients", status_code=201)
def create_ingredient(
    payload: IngredientCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    if db.scalar(select(Ingredient).where(Ingredient.name.ilike(payload.name.strip()))):
        raise HTTPException(status_code=409, detail="Ingredient already exists")
    item = Ingredient(
        name=payload.name.strip(),
        description=payload.description,
        common_uses=payload.common_uses,
        benefits=payload.benefits,
        cautions=payload.cautions,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
