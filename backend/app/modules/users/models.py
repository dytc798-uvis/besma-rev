from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now
from app.core.enums import Role, UIType


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    login_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    birth_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.SITE)
    ui_type: Mapped[UIType] = mapped_column(Enum(UIType), nullable=False, default=UIType.SITE)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    map_preference: Mapped[str | None] = mapped_column(String(20), nullable=True, default="NAVER", server_default="NAVER")
    # Initial-login password must be changed before accessing other services.
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    site: Mapped["Site"] = relationship(
        "Site",
        back_populates="users",
        foreign_keys="User.site_id",
    )

