from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.permissions import Permission, role_has_permission
from app.auth.security import decode_token
from app.core.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "NOT_AUTHENTICATED", "message": "Not authenticated"}},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise credentials_exception from exc

    if payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_permission(permission: Permission):
    def _checker(user: User = Depends(get_current_user)) -> User:
        if not role_has_permission(user.role_names, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"Missing required permission: {permission.value}",
                    }
                },
            )
        return user

    return _checker
