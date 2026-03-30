from io import BytesIO
from pathlib import Path
import sys

from fastapi.testclient import TestClient

# backend/에서 실행된다고 가정하고, app.* import를 위해 현재 경로를 sys.path에 추가
sys.path.insert(0, ".")

from app.main import app
from app.config.settings import settings
from app.core.auth import get_current_user
from app.core.database import SessionLocal
from app.core.enums import Role, UIType
from app.modules.users.models import User
from app.modules.sites.models import Site, SiteImportBatch


def main() -> None:
    # storage_root를 테스트용 디렉터리로 변경
    settings.storage_root = Path("storage_test")
    settings.storage_root.mkdir(parents=True, exist_ok=True)

    client = TestClient(app)

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.login_id == "hqsafe1").first()
        if not user:
            site = session.query(Site).first()
            user = User(
                name="APITester",
                login_id="api_tester",
                password_hash="x",
                department="QA",
                role=Role.HQ_OTHER,
                ui_type=UIType.HQ_OTHER,
                site_id=site.id if site else None,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        # dependency override로 인증 우회
        def override_get_current_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = override_get_current_user

        # 간단한 엑셀 생성
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["현장코드", "공사명", "공사기간", "도급금액"])
        ws.append(["SITE_API_01", "API 테스트 현장", "2022-01-24 ~ 2025-11-10", "6,829,000,000"])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        files = {
            "file": (
                "sites.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        resp = client.post("/sites/import", files=files)
        print("STATUS", resp.status_code)
        print("JSON", resp.json())

        batch = session.query(SiteImportBatch).order_by(SiteImportBatch.id.desc()).first()
        site = session.query(Site).filter(Site.site_code == "SITE_API_01").first()
        print(
            "BATCH",
            batch.id if batch else None,
            batch.total_rows if batch else None,
            batch.created_rows if batch else None,
            batch.updated_rows if batch else None,
            batch.failed_rows if batch else None,
        )
        print(
            "SITE",
            site.site_code if site else None,
            site.project_amount if site else None,
            site.created_by_user_id if site else None,
            site.updated_by_user_id if site else None,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()

