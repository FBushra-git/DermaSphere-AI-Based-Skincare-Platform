from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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
    UserSkinProfile,
    product_ingredients,
    product_skin_concerns,
    product_skin_types,
    profile_skin_concerns,
)
from app.schemas import CatalogRecordUpdate, IngredientCreate, NamedRecord

router = APIRouter(tags=["catalog"])


@router.get("/api/admin/categories")
def list_all_categories(
    db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))
):
    return db.scalars(select(Category).order_by(Category.name)).all()


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


@router.patch("/api/admin/categories/{category_id}")
def update_category(
    category_id: str,
    payload: CatalogRecordUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    item = db.get(Category, category_id)
    if not item:
        raise HTTPException(status_code=404, detail="Category not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and db.scalar(
        select(Category.id).where(
            Category.id != item.id, Category.name.ilike(changes["name"].strip())
        )
    ):
        raise HTTPException(status_code=409, detail="Category already exists")
    for field, value in changes.items():
        setattr(item, field, value.strip() if field == "name" and value else value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/api/admin/categories/{category_id}", status_code=204)
def deactivate_category(
    category_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    item = db.get(Category, category_id)
    if not item:
        raise HTTPException(status_code=404, detail="Category not found")
    item.is_active = False
    db.commit()


@router.patch("/api/admin/skin-types/{skin_type_id}")
def update_skin_type(
    skin_type_id: str,
    payload: CatalogRecordUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    item = db.get(SkinType, skin_type_id)
    if not item:
        raise HTTPException(status_code=404, detail="Skin type not found")
    if payload.name and db.scalar(
        select(SkinType.id).where(
            SkinType.id != item.id, SkinType.name.ilike(payload.name.strip())
        )
    ):
        raise HTTPException(status_code=409, detail="Skin type already exists")
    changes = payload.model_dump(exclude_unset=True, exclude={"is_active"})
    for field, value in changes.items():
        setattr(item, field, value.strip() if field == "name" and value else value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/api/admin/skin-types/{skin_type_id}", status_code=204)
def delete_skin_type(
    skin_type_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    item = db.get(SkinType, skin_type_id)
    if not item:
        raise HTTPException(status_code=404, detail="Skin type not found")
    used_by_profile = db.scalar(
        select(func.count())
        .select_from(UserSkinProfile)
        .where(UserSkinProfile.skin_type_id == item.id)
    )
    used_by_product = db.scalar(
        select(func.count())
        .select_from(product_skin_types)
        .where(product_skin_types.c.skin_type_id == item.id)
    )
    if used_by_profile or used_by_product:
        raise HTTPException(
            status_code=409, detail="Skin type is referenced by a profile or product"
        )
    db.delete(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Skin type is referenced by a profile or product"
        ) from exc


@router.patch("/api/admin/skin-concerns/{concern_id}")
def update_skin_concern(
    concern_id: str,
    payload: CatalogRecordUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    item = db.get(SkinConcern, concern_id)
    if not item:
        raise HTTPException(status_code=404, detail="Skin concern not found")
    if payload.name and db.scalar(
        select(SkinConcern.id).where(
            SkinConcern.id != item.id, SkinConcern.name.ilike(payload.name.strip())
        )
    ):
        raise HTTPException(status_code=409, detail="Skin concern already exists")
    changes = payload.model_dump(exclude_unset=True, exclude={"is_active"})
    for field, value in changes.items():
        setattr(item, field, value.strip() if field == "name" and value else value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/api/admin/skin-concerns/{concern_id}", status_code=204)
def delete_skin_concern(
    concern_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    item = db.get(SkinConcern, concern_id)
    if not item:
        raise HTTPException(status_code=404, detail="Skin concern not found")
    used_by_product = db.scalar(
        select(func.count())
        .select_from(product_skin_concerns)
        .where(product_skin_concerns.c.skin_concern_id == item.id)
    )
    used_by_profile = db.scalar(
        select(func.count())
        .select_from(profile_skin_concerns)
        .where(profile_skin_concerns.c.skin_concern_id == item.id)
    )
    if used_by_profile or used_by_product:
        raise HTTPException(
            status_code=409, detail="Skin concern is referenced by a profile or product"
        )
    db.delete(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Skin concern is referenced by a profile or product"
        ) from exc


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
