from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config.settings import settings
from app.core.database import Base


# Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _load_model_metadata() -> None:
    """
    FK/테이블 생성 순서 문제를 피하기 위해, Base.metadata에 모든 모델을 등록한다.
    (init_db()는 create_all을 수행하므로 여기서는 호출하지 않는다)
    """
    from app.modules.users import models as _user_models  # noqa: F401
    from app.modules.sites import models as _site_models  # noqa: F401
    from app.modules.documents import models as _document_models  # noqa: F401
    from app.modules.approvals import models as _approval_models  # noqa: F401
    from app.modules.opinions import models as _opinion_models  # noqa: F401
    from app.modules.document_settings import models as _document_settings_models  # noqa: F401
    from app.modules.document_generation import models as _document_generation_models  # noqa: F401
    from app.modules.document_submissions import models as _document_submissions_models  # noqa: F401
    from app.modules.law_registry import models as _law_registry_models  # noqa: F401
    from app.modules.communications import models as _communications_models  # noqa: F401


_load_model_metadata()
target_metadata = Base.metadata


def _get_sqlalchemy_url() -> str:
    # 우선순위:
    # 1) BESMA_ALEMBIC_DB_URL (완전 URL)
    # 2) BESMA_SQLITE_PATH (sqlite 파일 경로)
    # 3) settings.sqlite_path
    import os

    url = os.getenv("BESMA_ALEMBIC_DB_URL")
    if url:
        return url

    override_path = os.getenv("BESMA_SQLITE_PATH")
    if override_path:
        db_path = Path(override_path).resolve()
        return f"sqlite:///{db_path}"

    db_path = Path(settings.sqlite_path).resolve()
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    url = _get_sqlalchemy_url()
    print(f"[alembic] target db = {url}")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_sqlalchemy_url()
    print(f"[alembic] target db = {configuration['sqlalchemy.url']}")

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,  # SQLite 제약 변경/컬럼 변경을 위한 batch mode
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

