from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.datetime_utils import utc_now


class WorkerFeedbackOpinion(Base):
    __tablename__ = "worker_feedback_opinions"
    __table_args__ = (UniqueConstraint("source_fingerprint", name="uq_worker_feedback_source_fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    submitted_at_raw: Mapped[str | None] = mapped_column(String(80), nullable=True)
    worker_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth6: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_masked: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone_normalized: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    opinion_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_site_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    matched_site_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    matched_site_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    matched_worker_id: Mapped[int | None] = mapped_column(
        ForeignKey("functional_eval_workers.id"), nullable=True, index=True
    )
    match_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unmatched", index=True)
    action_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    site_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    action_taken_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    action_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    appropriateness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actionability_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prevention_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_total: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    bonus_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_awarded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    bonus_awarded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    route: Mapped[str] = mapped_column(String(50), nullable=False, default="QR코드")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
