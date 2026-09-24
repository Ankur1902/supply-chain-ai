from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Role(Base, TimestampMixin):
    """
    Roles: admin, operations_manager, analyst, viewer.
    Permission enforcement lives in app/auth/permissions.py, keyed off role name.
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="role")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def role_names(self) -> list[str]:
        return [ur.role.name for ur in self.user_roles]


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates="user_roles")
