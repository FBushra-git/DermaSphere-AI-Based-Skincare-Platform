from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import Category, Ingredient, Role, SkinConcern, SkinType, User
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
