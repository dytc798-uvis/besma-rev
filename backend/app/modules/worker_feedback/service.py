from sqlalchemy import inspect, text

from app.core.database import engine


def ensure_schema() -> None:
    inspector = inspect(engine)
    if "worker_feedback_opinions" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("worker_feedback_opinions")}
    additions = {
        "submitted_site_name": "VARCHAR(500)",
        "matched_worker_id": "INTEGER",
        "site_received_at": "DATETIME",
        "appropriateness_score": "INTEGER",
        "actionability_score": "INTEGER",
        "prevention_score": "INTEGER",
        "score_total": "INTEGER",
        "bonus_points": "INTEGER NOT NULL DEFAULT 0",
        "bonus_awarded_at": "DATETIME",
        "bonus_awarded_by_user_id": "INTEGER",
    }
    with engine.begin() as conn:
        for name, ddl_type in additions.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE worker_feedback_opinions ADD COLUMN {name} {ddl_type}"))
