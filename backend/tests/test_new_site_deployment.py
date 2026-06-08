from __future__ import annotations

from app.modules.new_site_deployment.deployment_alias import derive_deployment_site_alias
from app.modules.new_site_deployment.service import _parse_administrators_payload, compute_requirement_labels


def test_parse_administrators_array():
    payload = {
        "administrators": [
            {"role": "SITE_MANAGER", "name": "홍길동"},
            {"role": "GONGMU", "name": "김공무"},
            {"role": "GONGMU", "name": "이공무"},
            {"role": "INVALID", "name": "무시"},
            {"role": "SAFETY", "name": ""},
        ]
    }
    admins = _parse_administrators_payload(payload)
    assert len(admins) == 3
    assert admins[0] == {"role": "SITE_MANAGER", "name": "홍길동"}
    assert admins[2] == {"role": "GONGMU", "name": "이공무"}


def test_parse_administrators_legacy_fields():
    payload = {
        "site_manager_name": "소장1",
        "gongmu_name": "공무1",
        "safety_name": "안전1",
    }
    admins = _parse_administrators_payload(payload)
    assert [a["role"] for a in admins] == ["SITE_MANAGER", "GONGMU", "SAFETY"]


def test_derive_alias_shinsegae_starfield_changwon():
    alias = derive_deployment_site_alias(
        "2.신세계건설",
        "스타필드 창원 신축 소방전기공사(1공구)",
    )
    assert alias == "신세계스타창원"


def test_requirement_labels_by_amount():
    assert "안전보건관리책임자" in compute_requirement_labels(6_000_000_000)[0]
    assert "안전관리자" in compute_requirement_labels(3_000_000_000)[0]
    assert any("관리감독자" in x for x in compute_requirement_labels(None))
