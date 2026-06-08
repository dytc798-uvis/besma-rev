"""기능인제 모듈 상수."""

from __future__ import annotations

# 10명 이하: 소장 전원 평가 / 11명 이상: 소장=직영, 팀장=팀원 평가 후 소장 전체 승인
TEAM_LEADER_SPLIT_THRESHOLD = 10

# 현장별 승인 단계: 소장 전체승인 → 안전보건실(HQ) → 대표이사(CEO)
APPROVAL_STATUS_IN_PROGRESS = "IN_PROGRESS"
APPROVAL_STATUS_SITE_APPROVED = "SITE_APPROVED"
APPROVAL_STATUS_HQ_APPROVED = "HQ_APPROVED"
APPROVAL_STATUS_CEO_APPROVED = "CEO_APPROVED"
APPROVAL_STATUS_REJECTED = "REJECTED"

APPROVAL_STATUS_LABELS: dict[str, str] = {
    APPROVAL_STATUS_IN_PROGRESS: "평가 진행",
    APPROVAL_STATUS_SITE_APPROVED: "소장 승인 · 본사 검토 대기",
    APPROVAL_STATUS_HQ_APPROVED: "안전보건실 승인 · 대표 최종 대기",
    APPROVAL_STATUS_CEO_APPROVED: "최종 승인 완료",
    APPROVAL_STATUS_REJECTED: "반려 · 수정 중",
}

# 기능인제 최종 승인(대표이사) 전용 로그인 ID
CEO_EVAL_LOGIN_IDS: frozenset[str] = frozenset({"부현대표-김홍수"})
