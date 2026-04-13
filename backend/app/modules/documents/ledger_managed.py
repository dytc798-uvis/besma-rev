"""관리대장 전용 문서 유형 — 문서취합에서는 참조만, 소통·승인·업로드는 전용 관리대장 화면에서."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from app.modules.documents.models import Document

LEDGER_MANAGED_DOCUMENT_TYPE_CODES = frozenset({"AUTO_WORKER_OPINION_LOG", "NONCONFORMITY_ACTION_REPORT"})

LEDGER_MANAGED_COMMUNICATION_MESSAGE = (
    "이 문서는 관리대장 전용 문서입니다. 전용 관리대장 화면에서 처리하세요."
)


def is_ledger_managed_document_type(document_type_code: str | None) -> bool:
    return (document_type_code or "").strip() in LEDGER_MANAGED_DOCUMENT_TYPE_CODES


def assert_not_ledger_managed_document(doc: "Document", *, operation: str = "this operation") -> None:
    """문서취합형 소통·승인·코멘트·이력 API에서 호출."""
    if is_ledger_managed_document_type(doc.document_type):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=LEDGER_MANAGED_COMMUNICATION_MESSAGE,
        )


def assert_not_ledger_managed_document_type(document_type_code: str | None) -> None:
    if is_ledger_managed_document_type(document_type_code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=LEDGER_MANAGED_COMMUNICATION_MESSAGE,
        )
