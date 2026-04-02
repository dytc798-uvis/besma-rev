from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.config.security import get_password_hash, verify_password
from app.core.enums import Role, UIType
from app.modules.sites.models import Site
from app.modules.users.models import User


HQ_DEMO_USERS: list[tuple[str, str]] = [
    ("정상익", "hq01"),
    ("엄재복", "hq02"),
    ("김복수", "hq03"),
    ("조동문", "hq04"),
    ("김홍수", "hq05"),
]

SITE_DEMO_USERS: list[tuple[str, str]] = [
    ("양규성", "site01"),
    ("박명식", "site02"),
    ("박규철", "site03"),
]


@dataclass
class DemoUserResult:
    name: str
    login_id: str
    role: str
    site_id: int | None
    verified_password: bool
    action: str


@dataclass
class DemoUserProvisionResult:
    site_id: int
    site_code: str
    site_name: str
    created_site: bool
    users: list[DemoUserResult]


def _site_code_aliases(site_code: str) -> list[str]:
    normalized = (site_code or "").strip()
    aliases = [normalized]
    if normalized:
        aliases.append(normalized.upper())
    if normalized.lower() == "site01":
        aliases.extend(["SITE001", "site001"])
    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        if not alias or alias in seen:
            continue
        seen.add(alias)
        deduped.append(alias)
    return deduped


def ensure_demo_site(db: Session, site_code: str = "site01") -> tuple[Site, bool]:
    site = None
    for alias in _site_code_aliases(site_code):
        site = db.query(Site).filter(Site.site_code == alias).first()
        if site is not None:
            return site, False

    site = Site(
        site_code=site_code,
        site_name="Demo Site 01",
        start_date=date.today(),
        status="ACTIVE",
        manager_name="데모현장관리자",
        description="임시 로그인 테스트용 데모 현장",
    )
    db.add(site)
    db.flush()
    return site, True


def _upsert_demo_user(
    db: Session,
    *,
    name: str,
    login_id: str,
    role: Role,
    ui_type: UIType,
    password: str,
    site_id: int | None,
    department: str,
) -> DemoUserResult:
    existing = db.query(User).filter(User.login_id == login_id).first()
    action = "updated" if existing else "created"
    password_hash = get_password_hash(password)

    if existing is None:
        existing = User(
            name=name,
            login_id=login_id,
            password_hash=password_hash,
            department=department,
            role=role,
            ui_type=ui_type,
            site_id=site_id,
            is_active=True,
            must_change_password=False,
        )
        db.add(existing)
    else:
        existing.name = name
        existing.password_hash = password_hash
        existing.department = department
        existing.role = role
        existing.ui_type = ui_type
        existing.site_id = site_id
        existing.is_active = True
        existing.must_change_password = False

    db.flush()
    return DemoUserResult(
        name=existing.name,
        login_id=existing.login_id,
        role=existing.role.value if hasattr(existing.role, "value") else str(existing.role),
        site_id=existing.site_id,
        verified_password=verify_password(password, existing.password_hash),
        action=action,
    )


def ensure_demo_login_users(
    db: Session,
    *,
    password: str = "temp@12",
    site_code: str = "SITE002",
) -> DemoUserProvisionResult:
    site, created_site = ensure_demo_site(db, site_code=site_code)
    preferred_c18_site = (
        db.query(Site)
        .filter(
            (Site.site_name.contains("C18BL")) | (Site.site_name.contains("청라C18")),
            Site.address.isnot(None),
            Site.address != "",
        )
        .order_by(Site.id.asc())
        .first()
    )
    site_for_site_users = preferred_c18_site or site

    results: list[DemoUserResult] = []
    for name, login_id in HQ_DEMO_USERS:
        results.append(
            _upsert_demo_user(
                db,
                name=name,
                login_id=login_id,
                role=Role.HQ_SAFE,
                ui_type=UIType.HQ_SAFE,
                password=password,
                site_id=None,
                department="안전보건실",
            )
        )

    for name, login_id in SITE_DEMO_USERS:
        results.append(
            _upsert_demo_user(
                db,
                name=name,
                login_id=login_id,
                role=Role.SITE,
                ui_type=UIType.SITE,
                password=password,
                site_id=site_for_site_users.id,
                department="현장",
            )
        )

    db.commit()
    return DemoUserProvisionResult(
        site_id=site_for_site_users.id,
        site_code=site_for_site_users.site_code,
        site_name=site_for_site_users.site_name,
        created_site=created_site,
        users=results,
    )
