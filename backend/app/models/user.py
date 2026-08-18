from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.attempt import Attempt
    from backend.app.models.tariff import Tariff, UserSubscription


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("student", "teacher", "admin", name="user_role", native_enum=False, validate_strings=True),
        nullable=False,
        default="student",
        server_default="student",
    )
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paid_tariff_id: Mapped[int | None] = mapped_column(
        ForeignKey("tariffs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    paid_tariff_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile: Mapped[UserProfile | None] = relationship(back_populates="user", uselist=False)
    attempts: Mapped[list[Attempt]] = relationship(back_populates="user")
    subscriptions: Mapped[list[UserSubscription]] = relationship(back_populates="user")
    paid_tariff: Mapped[Tariff | None] = relationship(back_populates="users_with_current_tariff")

    @property
    def paid_tariff_title(self) -> str | None:
        return self.paid_tariff.title if self.paid_tariff else None

    @property
    def paid_tariff_code(self) -> str | None:
        return self.paid_tariff.code if self.paid_tariff else None


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_profiles_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    school: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    # PostgreSQL migration note: replace Text with JSONB.
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")
