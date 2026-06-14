"""제재 근거·서명·감점 테스트."""

from __future__ import annotations

from app.modules.functional_eval.sanction_evidence import (
    DEFAULT_SANCTION_PENALTY_POINTS,
    EVIDENCE_COMMENT,
    EVIDENCE_PHOTO,
)


def test_default_sanction_penalty_points():
    assert DEFAULT_SANCTION_PENALTY_POINTS == 5


def test_evidence_type_constants():
    assert EVIDENCE_COMMENT == "COMMENT"
    assert EVIDENCE_PHOTO == "PHOTO"
