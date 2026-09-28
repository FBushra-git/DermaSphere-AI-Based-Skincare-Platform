from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Product, ProductStatus, Role, Routine, User, routine_products
from app.schemas import RoutineCreate, RoutineItemInput, RoutineUpdate

router = APIRouter(prefix="/api/routines", tags=["skincare routines"])


def owned_routine(db: Session, routine_id: str, user: User) -> Routine:
    routine = db.scalar(
        select(Routine).where(Routine.id == routine_id, Routine.user_id == user.id)
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    return routine


def routine_view(db: Session, routine: Routine):
    rows = db.execute(
        select(
            Product.id,
            Product.name,
            Product.brand,
            Product.image_url,
            routine_products.c.sequence,
            routine_products.c.step_note,
        )
        .join(Product, Product.id == routine_products.c.product_id)
        .where(routine_products.c.routine_id == routine.id)
        .order_by(routine_products.c.sequence)
    ).all()
    return {
        "id": routine.id,
        "name": routine.name,
        "description": routine.description,
        "routine_type": routine.routine_type,
        "products": [
            {
                "id": row.id,
                "name": row.name,
                "brand": row.brand,
                "image_url": row.image_url,
                "sequence": row.sequence,
                "step_note": row.step_note,
            }
            for row in rows
        ],
    }


@router.get("")
def list_routines(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if user.role == Role.ADMIN:
        raise HTTPException(
            status_code=403, detail="Routines belong to customer accounts"
        )
    routines = db.scalars(
        select(Routine)
        .where(Routine.user_id == user.id)
        .order_by(Routine.created_at.desc())
    ).all()
    return [routine_view(db, routine) for routine in routines]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_routine(
    payload: RoutineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == Role.ADMIN:
        raise HTTPException(
            status_code=403, detail="Routines belong to customer accounts"
        )
    routine = Routine(
        user_id=user.id,
        name=payload.name.strip(),
        description=payload.description,
        routine_type=payload.routine_type,
    )
    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine_view(db, routine)


@router.patch("/{routine_id}")
def update_routine(
    routine_id: str,
    payload: RoutineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    routine = owned_routine(db, routine_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(routine, field, value.strip() if field == "name" and value else value)
    db.commit()
    db.refresh(routine)
    return routine_view(db, routine)


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(
    routine_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    routine = owned_routine(db, routine_id, user)
    db.delete(routine)
    db.commit()


@router.post("/{routine_id}/products", status_code=status.HTTP_201_CREATED)
def add_routine_product(
    routine_id: str,
    payload: RoutineItemInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    routine = owned_routine(db, routine_id, user)
    product = db.get(Product, payload.product_id)
    if not product or product.status != ProductStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Approved product not found")
    exists = db.execute(
        select(routine_products.c.product_id).where(
            routine_products.c.routine_id == routine.id,
            routine_products.c.product_id == product.id,
        )
    ).first()
    if exists:
        raise HTTPException(
            status_code=409, detail="Product is already in this routine"
        )
    db.execute(
        routine_products.insert().values(
            routine_id=routine.id,
            product_id=product.id,
            sequence=payload.sequence,
            step_note=payload.step_note,
        )
    )
    db.commit()
    return routine_view(db, routine)


@router.patch("/{routine_id}/products/{product_id}")
def reorder_routine_product(
    routine_id: str,
    product_id: str,
    payload: RoutineItemInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    routine = owned_routine(db, routine_id, user)
    if payload.product_id != product_id:
        raise HTTPException(status_code=422, detail="Product ID must match the route")
    result = db.execute(
        update(routine_products)
        .where(
            routine_products.c.routine_id == routine.id,
            routine_products.c.product_id == product_id,
        )
        .values(sequence=payload.sequence, step_note=payload.step_note)
    )
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Product is not in this routine")
    db.commit()
    return routine_view(db, routine)


@router.delete(
    "/{routine_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_routine_product(
    routine_id: str,
    product_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    routine = owned_routine(db, routine_id, user)
    result = db.execute(
        routine_products.delete().where(
            routine_products.c.routine_id == routine.id,
            routine_products.c.product_id == product_id,
        )
    )
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Product is not in this routine")
    db.commit()
