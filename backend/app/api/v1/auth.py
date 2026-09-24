from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.common.responses import success
from app.core.config import get_settings
from app.core.database import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ACCOUNT_DISABLED", "message": "Account is disabled"}},
        )

    roles = user.role_names
    access_token = create_access_token(str(user.id), roles)
    refresh_token = create_refresh_token(str(user.id))

    db.add(AuditLog(user_id=user.id, action="login", entity_type="user", entity_id=user.id, details={}))
    db.commit()

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
    return success(token_response.model_dump())


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired refresh token"}},
        ) from exc

    if decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Not a refresh token"}},
        )

    user = db.get(User, int(decoded["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "User no longer active"}},
        )

    access_token = create_access_token(str(user.id), user.role_names)
    new_refresh_token = create_refresh_token(str(user.id))
    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
    return success(token_response.model_dump())


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return success(UserOut.model_validate({**current_user.__dict__, "roles": current_user.role_names}).model_dump())


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="logout",
            entity_type="user",
            entity_id=current_user.id,
            details={},
        )
    )
    db.commit()
    return success({"message": "Logged out"})
