from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import (
    Role,
    SkinConcern,
    SkinType,
    User,
    UserSkinProfile,
    profile_skin_concerns,
)
from app.schemas import ProfileUpdate

router = APIRouter(prefix="/api/users", tags=["customer profile"])


@router.get("/profile/skin")
def get_skin_profile(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    profile = db.scalar(
        select(UserSkinProfile).where(UserSkinProfile.user_id == user.id)
    )
    if not profile:
        return {
            "skin_type": None,
            "skin_concerns": [],
            "budget_min": None,
            "budget_max": None,
            "preferences": None,
        }
    skin_type = db.get(SkinType, profile.skin_type_id) if profile.skin_type_id else None
    concerns = db.execute(
        select(SkinConcern.id, SkinConcern.name)
        .join(profile_skin_concerns)
        .where(profile_skin_concerns.c.profile_id == profile.id)
    ).all()
    return {
        "skin_type": {"id": skin_type.id, "name": skin_type.name}
        if skin_type
        else None,
        "skin_concerns": [{"id": row.id, "name": row.name} for row in concerns],
        "budget_min": profile.budget_min,
        "budget_max": profile.budget_max,
        "preferences": profile.preferences,
    }


@router.put("/profile/skin")
def update_skin_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == Role.ADMIN:
        raise HTTPException(
            status_code=403, detail="This profile belongs to a customer account"
        )
    if (
        payload.budget_min is not None
        and payload.budget_max is not None
        and payload.budget_min > payload.budget_max
    ):
        raise HTTPException(
            status_code=422, detail="Minimum budget cannot exceed maximum budget"
        )
    if payload.skin_type_id and not db.get(SkinType, payload.skin_type_id):
        raise HTTPException(status_code=422, detail="Skin type does not exist")
    known = (
        set(
            db.scalars(
                select(SkinConcern.id).where(
                    SkinConcern.id.in_(payload.skin_concern_ids)
                )
            ).all()
        )
        if payload.skin_concern_ids
        else set()
    )
    if known != set(payload.skin_concern_ids):
        raise HTTPException(
            status_code=422, detail="One or more skin concerns do not exist"
        )
    profile = db.scalar(
        select(UserSkinProfile).where(UserSkinProfile.user_id == user.id)
    )
    if not profile:
        profile = UserSkinProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    profile.skin_type_id = payload.skin_type_id
    profile.budget_min = payload.budget_min
    profile.budget_max = payload.budget_max
    profile.preferences = payload.preferences
    db.execute(
        profile_skin_concerns.delete().where(
            profile_skin_concerns.c.profile_id == profile.id
        )
    )
    if payload.skin_concern_ids:
        db.execute(
            profile_skin_concerns.insert(),
            [
                {"profile_id": profile.id, "skin_concern_id": item}
                for item in dict.fromkeys(payload.skin_concern_ids)
            ],
        )
    db.commit()
    return get_skin_profile(db, user)
