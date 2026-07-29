from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.enums import Role
from app.core.permissions import assert_document_file_access


def _user(role: Role, site_id: int | None = None):
    return SimpleNamespace(role=role, site_id=site_id)


@pytest.mark.parametrize(
    "role",
    [Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN, Role.ACCIDENT_ADMIN],
)
def test_hq_safety_workspace_can_read_any_site_file(role):
    assert_document_file_access(_user(role), site_id=999)


@pytest.mark.parametrize("role", [Role.SITE, Role.SITE_FUNCTIONAL_EVAL])
def test_site_role_can_read_own_site_only(role):
    assert_document_file_access(_user(role, 8), site_id=8)
    with pytest.raises(HTTPException) as exc:
        assert_document_file_access(_user(role, 8), site_id=9)
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "role",
    [
        Role.HQ_OTHER,
        Role.WORKER,
        Role.FUNCTIONAL_EVAL_VIEWER,
        Role.HQ_BUDGET_ESTIMATE,
        Role.HQ_OUTSOURCING_PURCHASE,
    ],
)
def test_non_document_roles_cannot_read_file_content(role):
    with pytest.raises(HTTPException) as exc:
        assert_document_file_access(_user(role, 8), site_id=8)
    assert exc.value.status_code == 403


def test_site_without_scope_is_denied():
    with pytest.raises(HTTPException) as exc:
        assert_document_file_access(_user(Role.SITE, None), site_id=8)
    assert exc.value.status_code == 403
