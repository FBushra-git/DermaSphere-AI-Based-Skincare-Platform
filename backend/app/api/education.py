from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import EducationalContent, Role, User
from app.schemas import ContentCreate, ContentUpdate

router = APIRouter(tags=["educational content"])


@router.get("/api/content")
def list_content(category: str | None = None, db: Session = Depends(get_db)):
    stmt = (
        select(EducationalContent)
        .where(EducationalContent.is_published.is_(True))
        .order_by(EducationalContent.created_at.desc())
    )
    if category:
        stmt = stmt.where(EducationalContent.category.ilike(category.strip()))
    return db.scalars(stmt.limit(100)).all()


@router.post("/api/admin/content", status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    item = EducationalContent(
        author_id=admin.id,
        title=payload.title.strip(),
        description=payload.description,
        category=payload.category.strip(),
        source=payload.source,
        url=str(payload.url) if payload.url else None,
        is_published=payload.is_published,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/api/admin/content/{content_id}")
def update_content(
    content_id: str,
    payload: ContentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    item = db.get(EducationalContent, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(
            item,
            field,
            str(value)
            if field == "url" and value
            else value.strip()
            if field in {"title", "category", "source"} and value
            else value,
        )
    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/api/admin/content/{content_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_content(
    content_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    item = db.get(EducationalContent, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    db.delete(item)
    db.commit()
