from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import app.main  # noqa: F401  # Register every ORM model before querying.
from sqlalchemy import text

from app.config.settings import settings
from app.core.database import SessionLocal
from app.core.datetime_utils import utc_now
from app.modules.safety_ledgers.models import SafetyCardExpense, SafetyVehicle, SafetyVehicleLog
from app.modules.safety_ledgers.routes import _export_paths


CARD_SCOPE = "SAFETY_SHARED"
PLATE_NUMBER = "181하8339"
LOGIN_ID = "안전보건-정상익"

RECEIPTS = (
    ("KakaoTalk_20260803_075542817.jpg", datetime(2026, 7, 29, 11, 49, 53), None, "뉴메카마트", 31_000, "간식비", "박카스·비타500"),
    ("KakaoTalk_20260803_075542817_01.jpg", datetime(2026, 7, 30, 7, 41, 18), None, "도림주유소", 81_000, "주유비", "휘발유 44.142L / 원승인 120,000원 취소 후 최종 승인 81,000원"),
    ("KakaoTalk_20260803_075542817_02.jpg", datetime(2026, 7, 30, 15, 24, 56), None, "세미즈", 13_500, "간식비", "음료 4잔"),
    ("KakaoTalk_20260803_075542817_03.jpg", datetime(2026, 7, 31, 10, 44, 19), "대우청라 C18BL", "하삼동커피 청라점", 6_300, "간식비", "대우청라 C18BL 현장 방문"),
    ("KakaoTalk_20260803_075542817_04.jpg", datetime(2026, 7, 31, 14, 23, 48), "대우청라 C18BL", "전주한식뷔페", 17_000, "중식비", "식대 2명 / 대우청라 C18BL 현장 방문"),
)


def store_image(source: Path, kind: str) -> str:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:24]
    target_dir = settings.storage_root / "safety-ledgers" / kind
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"manual-{digest}{source.suffix.lower()}"
    if not target.exists():
        shutil.copy2(source, target)
    return str(target.relative_to(settings.storage_root)).replace("\\", "/")


def main(stage: Path) -> None:
    db = SessionLocal()
    inserted_cards = 0
    inserted_vehicle = 0
    updated_vehicle = 0
    try:
        user = db.execute(
            text("SELECT id, name FROM users WHERE login_id = :login_id"),
            {"login_id": LOGIN_ID},
        ).mappings().one()
        actor = SimpleNamespace(id=user["id"], name=user["name"])
        vehicle = db.query(SafetyVehicle).filter_by(plate_number=PLATE_NUMBER).one()

        for original_name, used_at, site_name, merchant, amount, description, note in RECEIPTS:
            source = stage / original_name
            if not source.is_file():
                raise FileNotFoundError(source)
            duplicate = (
                db.query(SafetyCardExpense)
                .filter_by(card_scope=CARD_SCOPE, receipt_original_name=original_name)
                .first()
            )
            if duplicate:
                continue
            db.add(
                SafetyCardExpense(
                    card_scope=CARD_SCOPE,
                    used_at=used_at,
                    site_name=site_name,
                    merchant=merchant,
                    amount=amount,
                    description=description,
                    card_last4="6925",
                    note=note,
                    receipt_image_path=store_image(source, "receipts"),
                    receipt_original_name=original_name,
                    extraction_status="CONFIRMED",
                    extraction_confidence=100,
                    extraction_raw_json=json.dumps({"source": "manual_verified_import", "confirmed": True}, ensure_ascii=False),
                    reviewed_at=utc_now(),
                    created_by_user_id=user["id"],
                )
            )
            inserted_cards += 1

        dashboard_name = "KakaoTalk_20260803_075542817_05.jpg"
        dashboard_source = stage / dashboard_name
        if not dashboard_source.is_file():
            raise FileNotFoundError(dashboard_source)
        dashboard_path = store_image(dashboard_source, "vehicle")
        reconstructed_logs = (
            (date(2026, 7, 28), "박영선", None, None, "서울 서대문구 북아현로1길(자택)↔롯데-인천효성지역; 거리 미확정(8/3 누적사진 기준 복원)"),
            (date(2026, 7, 29), "박영선", None, None, "서울 서대문구 북아현로1길(자택)↔대우-장위6구역; 거리 미확정(8/3 누적사진 기준 복원)"),
            (date(2026, 7, 31), "정상익", None, 70.0, "후곡마을(자택)↔대우청라 C18BL; 편도 35km, 왕복 70km"),
            (
                date(2026, 8, 3),
                "정상익",
                561,
                222.0,
                "후곡마을(자택)→회사 도착 후 촬영; 222km는 7/28·7/29·8/3 미배분 누적분, 전체 증가 292km 중 7/31 확정 70km 제외",
            ),
        )
        for driven_on, driver_name, odometer_km, trip_km, purpose in reconstructed_logs:
            original_name = (
                dashboard_name
                if driven_on == date(2026, 8, 3)
                else f"{driven_on:%Y%m%d}_누적복원_{dashboard_name}"
            )
            duplicate_log = (
                db.query(SafetyVehicleLog)
                .filter_by(vehicle_id=vehicle.id, dashboard_original_name=original_name)
                .first()
            )
            if duplicate_log:
                duplicate_log.driven_on = driven_on
                duplicate_log.driver_name = driver_name
                duplicate_log.odometer_km = odometer_km
                duplicate_log.trip_km = trip_km
                duplicate_log.purpose = purpose
                db.add(duplicate_log)
                updated_vehicle += 1
                continue
            db.add(
                SafetyVehicleLog(
                    vehicle_id=vehicle.id,
                    driven_on=driven_on,
                    driver_name=driver_name,
                    odometer_km=odometer_km,
                    trip_km=trip_km,
                    purpose=purpose,
                    dashboard_image_path=dashboard_path,
                    dashboard_original_name=original_name,
                    extraction_status="CONFIRMED",
                    extraction_confidence=100,
                    extraction_raw_json=json.dumps(
                        {"source": "manual_verified_import", "odometer_km": 561, "previous_odometer_km": 269},
                        ensure_ascii=False,
                    ),
                    reviewed_at=utc_now(),
                    created_by_user_id=user["id"],
                )
            )
            inserted_vehicle += 1

        db.commit()
        card_path, vehicle_path = _export_paths(db, actor)
        print(json.dumps({
            "inserted_cards": inserted_cards,
            "inserted_vehicle": inserted_vehicle,
            "updated_vehicle": updated_vehicle,
            "card_export": str(card_path),
            "vehicle_export": str(vehicle_path),
        }, ensure_ascii=False))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
