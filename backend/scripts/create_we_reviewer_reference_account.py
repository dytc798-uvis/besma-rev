"""Create or upsert 위레이저 기준 레퍼런스 계정.

Usage:
  cd backend
  PYTHONPATH=. python scripts/create_we_reviewer_reference_account.py --dry-run
  PYTHONPATH=. python scripts/create_we_reviewer_reference_account.py --apply

Default target account:
  login_id: 어드민
  password: boohyun2026!

This script intentionally follows the existing auth model and only creates
or updates one reference account row. It does not run migrations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config.security import get_password_hash  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.enums import Role, UIType  # noqa: E402
from app.modules.users.models import User  # noqa: E402


REFERENCE_LOGIN_ID = "어드민"
REFERENCE_NAME = "위레이저 참고용"
REFERENCE_PASSWORD = "boohyun2026!"
REFERENCE_ROLE = Role.ACCIDENT_ADMIN
REFERENCE_UI_TYPE = UIType.HQ_SAFE


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reference 계정 생성/검증")
    parser.add_argument("--dry-run", action="store_true", help="변경 없이 계획 출력")
    parser.add_argument("--apply", action="store_true", help="실제 upsert 수행")
    parser.add_argument(
        "--role",
        default=REFERENCE_ROLE.value,
        help=f"할당할 role (기본: {REFERENCE_ROLE.value})",
    )
    parser.add_argument(
        "--ui-type",
        default=REFERENCE_UI_TYPE.value,
        help=f"할당할 ui_type (기본: {REFERENCE_UI_TYPE.value})",
    )
    return parser.parse_args()


def _resolve_role(raw: str) -> Role:
    try:
        return Role(raw)
    except ValueError as exc:  # pragma: no cover - defensive path
        choices = ", ".join(r.value for r in Role)
        raise SystemExit(f"Invalid role {raw}. choose one of: {choices}") from exc


def _resolve_ui_type(raw: str) -> UIType:
    try:
        return UIType(raw)
    except ValueError as exc:  # pragma: no cover - defensive path
        choices = ", ".join(u.value for u in UIType)
        raise SystemExit(f"Invalid ui_type {raw}. choose one of: {choices}") from exc


def apply_reference_account(*, role: Role, ui_type: UIType, do_apply: bool) -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.login_id == REFERENCE_LOGIN_ID).first()

        if user is None:
            if not do_apply:
                print(
                    f"PLAN create: login_id={REFERENCE_LOGIN_ID} name={REFERENCE_NAME} "
                    f"role={role.value} ui_type={ui_type.value} must_change_password=False"
                )
                return

            user = User(
                name=REFERENCE_NAME,
                login_id=REFERENCE_LOGIN_ID,
                password_hash=get_password_hash(REFERENCE_PASSWORD),
                role=role,
                ui_type=ui_type,
                site_id=None,
                must_change_password=False,
                is_active=True,
            )
            db.add(user)
            action_text = "created"
        else:
            if do_apply:
                user.name = REFERENCE_NAME
                user.password_hash = get_password_hash(REFERENCE_PASSWORD)
                user.role = role
                user.ui_type = ui_type
                user.site_id = None
                user.must_change_password = False
                user.is_active = True
                db.add(user)
                action_text = "updated"
            else:
                action_text = (
                    f"PLAN update: login_id={REFERENCE_LOGIN_ID} existing_user_id={user.id} "
                    f"role={user.role.value if hasattr(user.role, 'value') else user.role} "
                    f"ui_type={user.ui_type.value if hasattr(user.ui_type, 'value') else user.ui_type} "
                    f"-> role={role.value}, ui_type={ui_type.value}, must_change_password=False"
                )

        if do_apply:
            db.commit()
            print(
                f"{action_text} login_id={REFERENCE_LOGIN_ID} role={role.value} "
                f"ui_type={ui_type.value} must_change_password=False"
            )
        else:
            print(action_text)
    finally:
        db.close()


def main() -> int:
    args = _parse_args()
    if not args.dry_run and not args.apply:
        raise SystemExit("Either --dry-run or --apply is required")

    if args.dry_run and args.apply:
        raise SystemExit("Specify only one of --dry-run or --apply")

    role = _resolve_role(args.role)
    ui_type = _resolve_ui_type(args.ui_type)
    apply_reference_account(role=role, ui_type=ui_type, do_apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
