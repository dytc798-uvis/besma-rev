"""신규현장 배포 — 예산견적·외주구매 팀 계정 생성.

비밀번호 초기값 1111, must_change_password=True (최초 로그인 시 변경 안내).

Usage:
  cd backend && PYTHONPATH=. python scripts/create_deployment_team_accounts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.security import get_password_hash  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.enums import Role, UIType  # noqa: E402
from app.modules.new_site_deployment import models as nsd_models  # noqa: F401, E402
from app.modules.users.models import User  # noqa: E402

INITIAL_PASSWORD = "1111"

BUDGET_ACCOUNTS: list[tuple[str, str]] = [
    ("손병휘", "예산견적-손병휘"),
    ("황순철", "예산견적-황순철"),
    ("곽상우", "예산견적-곽상우"),
    ("김정남", "예산견적-김정남"),
    ("김동민", "예산견적-김동민"),
]

PROCUREMENT_ACCOUNTS: list[tuple[str, str]] = [
    ("김용원", "외주구매-김용원"),
    ("박진균", "외주구매-박진균"),
    ("강익종", "외주구매-강익종"),
    ("홍소민", "외주구매-홍소민"),
    ("신영석", "외주구매-신영석"),
    ("주창오", "외주구매-주창오"),
]

CONSTRUCTION_MANAGEMENT_ACCOUNTS: list[tuple[str, str]] = [
    ("이재용", "공사관리-이재용"),
    ("전용성", "공사관리-전용성"),
    ("강태원", "공사관리-강태원"),
    ("김종현", "공사관리-김종현"),
    ("박성수", "공사관리-박성수"),
]


def _upsert(db, *, name: str, login_id: str, role: Role, department: str) -> None:
    user = db.query(User).filter(User.login_id == login_id).first()
    if user is None:
        user = User(
            name=name,
            login_id=login_id,
            password_hash=get_password_hash(INITIAL_PASSWORD),
            role=role,
            ui_type=UIType.HQ_SAFE,
            site_id=None,
            department=department,
            must_change_password=True,
            is_active=True,
        )
        db.add(user)
        action = "created"
    else:
        user.name = name
        user.password_hash = get_password_hash(INITIAL_PASSWORD)
        user.role = role
        user.ui_type = UIType.HQ_SAFE
        user.department = department
        user.must_change_password = True
        user.is_active = True
        db.add(user)
        action = "updated"
    db.flush()
    print(f"{action} {login_id} ({name}) role={role.value} must_change_password=True")


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        for name, login_id in BUDGET_ACCOUNTS:
            _upsert(db, name=name, login_id=login_id, role=Role.HQ_BUDGET_ESTIMATE, department="예산견적팀")
        for name, login_id in PROCUREMENT_ACCOUNTS:
            _upsert(
                db,
                name=name,
                login_id=login_id,
                role=Role.HQ_OUTSOURCING_PURCHASE,
                department="외주구매팀",
            )
        for name, login_id in CONSTRUCTION_MANAGEMENT_ACCOUNTS:
            _upsert(
                db,
                name=name,
                login_id=login_id,
                role=Role.HQ_OUTSOURCING_PURCHASE,
                department="공사관리팀",
            )
        db.commit()
        print("done - initial password 1111, must_change_password on first login")
    finally:
        db.close()


if __name__ == "__main__":
    main()
