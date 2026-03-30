from app.modules.document_settings import constants


def _public_constant_values(cls: type) -> set[str]:
    out: set[str] = set()
    for k, v in vars(cls).items():
        if k.startswith("_"):
            continue
        if not isinstance(v, str):
            continue
        out.add(v)
    return out


def test_rule_status_reason_values_match_valid_set_and_are_name_equal():
    values = _public_constant_values(constants.RuleStatusReason)

    # "고정값 집합 변경"이 발생하면 여기서 즉시 깨져야 함
    expected = {
        "DOC_TYPE_INACTIVE_OR_MISSING",
        "SITE_DISABLED",
        "MASTER_DEFAULT",
        "SITE_OVERRIDE",
        "CYCLE_INACTIVE",
        "CYCLE_MANUAL_ONLY",
        "MISSING_RULE",
        "SLOT_NOT_RESOLVED",
        "EXCEPTION",
        "DOCUMENT_LINK_BROKEN",
    }
    assert values == expected

    # VALID_STATUS_REASONS도 단일 진실 소스로서 동일해야 함
    assert constants.VALID_STATUS_REASONS == expected

    # 값은 관례적으로 key(name)와 동일해야 함 (리네임/오타 즉시 탐지)
    for k, v in vars(constants.RuleStatusReason).items():
        if k.startswith("_"):
            continue
        if isinstance(v, str):
            assert v == k

