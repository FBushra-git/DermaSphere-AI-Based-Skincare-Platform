from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Role, SellerProfile, User
from app.schemas import LoginInput, TokenRead, UserCreate, UserRead

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=TokenRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> TokenRead:
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        )
    role = Role(payload.role)
    if role == Role.SELLER and not payload.store_name:
        raise HTTPException(status_code=422, detail="Sellers must provide a store name")
    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.flush()
    if role == Role.SELLER:
        db.add(SellerProfile(user_id=user.id, store_name=payload.store_name.strip()))
    db.commit()
    db.refresh(user)
    return TokenRead(
        access_token=create_access_token(user.id), user=UserRead.model_validate(user)
    )


@router.post("/login", response_model=TokenRead)
def login(payload: LoginInput, db: Session = Depends(get_db)) -> TokenRead:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if (
        not user
        or not verify_password(payload.password, user.password_hash)
        or not user.is_active
    ):
        raise HTTPException(
            status_code=401,
            detail="Email or password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenRead(
        access_token=create_access_token(user.id), user=UserRead.model_validate(user)
    )


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user
