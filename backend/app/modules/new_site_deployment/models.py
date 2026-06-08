from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class NewSiteDeployment(Base):
    """예산견적팀이 등록하는 신규 현장."""

    __tablename__ = "new_site_deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True, index=True)
    site_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    site_alias: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    contractor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    site_name: Mapped[str] = mapped_column(String(300), nullable=False)
    construction_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    construction_period: Mapped[str | None] = mapped_column(String(200), nullable=True)

    site_manager_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gongmu_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    safety_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    construction_supervisor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    site_manager_login_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gongmu_login_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    container_arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    safety_checks_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    photos: Mapped[list["NewSiteDeploymentPhoto"]] = relationship(
        "NewSiteDeploymentPhoto", back_populates="deployment", cascade="all, delete-orphan"
    )
    documents: Mapped[list["NewSiteDeploymentDocument"]] = relationship(
        "NewSiteDeploymentDocument", back_populates="deployment", cascade="all, delete-orphan"
    )
    administrators: Mapped[list["NewSiteDeploymentAdministrator"]] = relationship(
        "NewSiteDeploymentAdministrator",
        back_populates="deployment",
        cascade="all, delete-orphan",
        order_by="NewSiteDeploymentAdministrator.sort_order",
    )


class NewSiteDeploymentAdministrator(Base):
    """신규 현장 배정 관리자(소장·공무 등) — 복수 등록."""

    __tablename__ = "new_site_deployment_administrators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("new_site_deployments.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    login_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    deployment: Mapped[NewSiteDeployment] = relationship("NewSiteDeployment", back_populates="administrators")


class NewSiteDeploymentPhoto(Base):
    """현장 — 배포 사인물 부착 사진."""

    __tablename__ = "new_site_deployment_photos"
    __table_args__ = (UniqueConstraint("deployment_id", "item_key", name="uq_nsd_photo_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("new_site_deployments.id"), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(50), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    deployment: Mapped[NewSiteDeployment] = relationship("NewSiteDeployment", back_populates="photos")


class NewSiteDeploymentDocument(Base):
    """현장 — 필요 서류 업로드."""

    __tablename__ = "new_site_deployment_documents"
    __table_args__ = (UniqueConstraint("deployment_id", "doc_type", name="uq_nsd_doc_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("new_site_deployments.id"), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    deployment: Mapped[NewSiteDeployment] = relationship("NewSiteDeployment", back_populates="documents")
