from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

from app.config.settings import settings
from app.core.database import init_db
from app.modules.auth.routes import router as auth_router
from app.modules.users.routes import router as users_router
from app.modules.sites.routes import router as sites_router
from app.modules.documents.routes import router as documents_router
from app.modules.approvals.routes import router as approvals_router
from app.modules.opinions.routes import router as opinions_router
from app.modules.dashboard.routes import router as dashboard_router
from app.modules.notifications.routes import router as notifications_router
from app.modules.document_settings.routes import router as document_settings_router
from app.modules.document_settings.routes import public_router as dynamic_menus_router
from app.modules.document_generation.routes import router as document_generation_router
from app.modules.document_explorer.routes import router as document_explorer_router
from app.modules.document_submissions.routes import router as document_submissions_ops_router
from app.modules.document_instances.routes import router as document_instances_router
from app.modules.workers.routes import router as workers_router
from app.modules.risk_library.routes import router as daily_work_plans_router
from app.modules.search.routes import router as search_router
from app.modules.law_registry.routes import router as law_registry_router
from app.modules.communications.routes import router as communications_router
from app.modules.notices.routes import router as notices_router
from app.modules.safety_policy_goals.routes import router as safety_policy_goals_router
from app.modules.safety_features.routes import router as safety_features_router


_original_request_form = Request.form


def _patched_request_form(self, *, max_files=1000, max_fields=1000, max_part_size=settings.upload_max_part_size_bytes):
    return _original_request_form(
        self,
        max_files=max_files,
        max_fields=max_fields,
        max_part_size=max_part_size,
    )


Request.form = _patched_request_form


def create_app() -> FastAPI:
    app = FastAPI(
        title="BESMA Local MVP Backend",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(sites_router)
    app.include_router(documents_router)
    app.include_router(approvals_router)
    app.include_router(opinions_router)
    app.include_router(dashboard_router)
    app.include_router(notifications_router)
    app.include_router(document_settings_router)
    app.include_router(dynamic_menus_router)
    app.include_router(document_generation_router)
    app.include_router(document_explorer_router)
    app.include_router(document_submissions_ops_router)
    app.include_router(document_instances_router)
    app.include_router(workers_router)
    app.include_router(daily_work_plans_router)
    app.include_router(search_router)
    app.include_router(law_registry_router)
    app.include_router(communications_router)
    app.include_router(notices_router)
    app.include_router(safety_policy_goals_router)
    app.include_router(safety_features_router)

    @app.on_event("startup")
    async def on_startup() -> None:
        init_db()

    @app.get("/health", tags=["system"])
    async def health_check() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
