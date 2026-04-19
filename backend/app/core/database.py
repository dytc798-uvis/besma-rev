from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{Path(settings.sqlite_path)}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    # 실제 모델들이 Base를 상속하도록 한 뒤 import 해야 함
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.risk_library import models as risk_library_models  # noqa: F401
    from app.modules.law_registry import models as law_registry_models  # noqa: F401
    from app.modules.communications import models as communications_models  # noqa: F401
    from app.modules.notices import models as notices_models  # noqa: F401
    from app.modules.safety_policy_goals import models as safety_policy_goal_models  # noqa: F401
    from app.modules.safety_features import models as safety_features_models  # noqa: F401
    from app.modules.accidents import models as accidents_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
