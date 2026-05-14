"""dedupe EMERGENCY_DRILL_REPORT rows per site (canonical + disable extras)

Revision ID: 20260514_0050
Revises: 20260514_0049
Create Date: 2026-05-14

운영 적용 전 **반드시** SQLite DB 백업 (예: cp database/besma.db /tmp/besma-$(date +%F).db).
본 리비전은 DELETE 없음; `document_upload_histories`는 건드리지 않는다.

배경
----
- `20260514_0049` 이후 일부 DB에서 `document_requirements`에 동일 code가 사이트별로 복수 행 생기면
  대시보드에 동일 문서가 두 줄로 나오고, `selected_requirement_id`가 옛 행을 가리키면
  새 행에서 이력이 비는 것처럼 보일 수 있다.
- `document_requirements`에는 UI용 `section`/`group_key` 컬럼이 없고,
  백엔드 `get_site_requirement_status`가 `frequency` 등으로 `site_display_bucket`을 계산한다.

정책 (idempotent)
-----------------
1. `code='EMERGENCY_DRILL_REPORT'`인 모든 행: `frequency='HALF_YEARLY'` 유지/정렬.
2. `site_id` 단위로 동일 code 행이 2개 이상일 때만 처리.
3. **canonical** 한 행 선택 (우선순위):
   - `document_instances.selected_requirement_id`가 가리키는 행이 있으면 그중 **가장 작은 id**
   - 없으면 `document_upload_histories` + `documents` (+ instance) 조합으로
     `GET /documents/history`와 동일한 OR 조건으로 닿는 이력이 있는 행 중 **가장 작은 id**
   - 그래도 없으면 해당 site에서 **가장 작은 id**
4. 비-canonical 행: 먼저 `document_instances.selected_requirement_id`를 canonical id로 갱신한 뒤
   `is_enabled=0` (DELETE 금지).
5. canonical 행: `is_enabled=1`, `frequency='HALF_YEARLY'`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text


revision = "20260514_0050"
down_revision = "20260514_0049"
branch_labels = None
depends_on = None

_CODE = "EMERGENCY_DRILL_REPORT"


def _history_count(
    conn,
    *,
    requirement_id: int,
    site_id: int,
    document_type_code: str,
) -> int:
    row = conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM document_upload_histories AS h
            JOIN documents AS d ON d.id = h.document_id
            LEFT JOIN document_instances AS di ON di.id = d.instance_id
            WHERE d.site_id = :site_id
              AND (
                di.selected_requirement_id = :requirement_id
                OR d.document_type = :req_code
                OR d.document_type = :dt_code
              )
            """
        ),
        {
            "site_id": site_id,
            "requirement_id": requirement_id,
            "req_code": _CODE,
            "dt_code": document_type_code,
        },
    ).scalar()
    return int(row or 0)


def _instance_ref_count(conn, *, requirement_id: int) -> int:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM document_instances WHERE selected_requirement_id = :requirement_id"
        ),
        {"requirement_id": requirement_id},
    ).scalar()
    return int(row or 0)


def _pick_canonical_id(conn, *, site_id: int, rows: list[dict]) -> int:
    """rows: list of {id, document_type_code} sorted by id ascending."""
    scored: list[tuple[int, int, int]] = []
    for r in rows:
        rid = int(r["id"])
        dtc = str(r["document_type_code"] or "")
        inst_n = _instance_ref_count(conn, requirement_id=rid)
        hist_n = _history_count(conn, requirement_id=rid, site_id=site_id, document_type_code=dtc)
        tier = 0 if inst_n > 0 else (1 if hist_n > 0 else 2)
        scored.append((tier, rid, rid))
    scored.sort(key=lambda t: (t[0], t[1]))
    return int(scored[0][2])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_requirements" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("document_requirements")}
    needed = {"id", "site_id", "code", "frequency", "is_enabled", "document_type_id"}
    if not needed.issubset(cols):
        return

    conn = bind

    conn.execute(
        text(
            """
            UPDATE document_requirements
            SET frequency = 'HALF_YEARLY'
            WHERE code = :code
            """
        ),
        {"code": _CODE},
    )

    dup_sites = conn.execute(
        text(
            """
            SELECT site_id, COUNT(*) AS n
            FROM document_requirements
            WHERE code = :code AND site_id IS NOT NULL
            GROUP BY site_id
            HAVING COUNT(*) > 1
            """
        ),
        {"code": _CODE},
    ).fetchall()

    for site_row in dup_sites:
        site_id = int(site_row[0])
        rows = conn.execute(
            text(
                """
                SELECT dr.id AS id, dtm.code AS document_type_code
                FROM document_requirements AS dr
                JOIN document_type_masters AS dtm ON dtm.id = dr.document_type_id
                WHERE dr.code = :code AND dr.site_id = :site_id
                ORDER BY dr.id ASC
                """
            ),
            {"code": _CODE, "site_id": site_id},
        ).mappings().all()
        if len(rows) < 2:
            continue
        row_dicts = [dict(r) for r in rows]
        canonical_id = _pick_canonical_id(conn, site_id=site_id, rows=row_dicts)
        other_ids = [int(r["id"]) for r in row_dicts if int(r["id"]) != canonical_id]

        for oid in other_ids:
            conn.execute(
                text(
                    """
                    UPDATE document_instances
                    SET selected_requirement_id = :canonical
                    WHERE selected_requirement_id = :old
                    """
                ),
                {"canonical": canonical_id, "old": oid},
            )

        for oid in other_ids:
            conn.execute(
                text(
                    """
                    UPDATE document_requirements
                    SET is_enabled = 0, frequency = 'HALF_YEARLY'
                    WHERE id = :id AND code = :code
                    """
                ),
                {"id": oid, "code": _CODE},
            )

        conn.execute(
            text(
                """
                UPDATE document_requirements
                SET is_enabled = 1, frequency = 'HALF_YEARLY'
                WHERE id = :id AND code = :code
                """
            ),
            {"id": canonical_id, "code": _CODE},
        )

    null_dup = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM document_requirements
            WHERE code = :code AND site_id IS NULL
            """
        ),
        {"code": _CODE},
    ).scalar()
    if int(null_dup or 0) > 1:
        rows = conn.execute(
            text(
                """
                SELECT dr.id AS id, dtm.code AS document_type_code
                FROM document_requirements AS dr
                JOIN document_type_masters AS dtm ON dtm.id = dr.document_type_id
                WHERE dr.code = :code AND dr.site_id IS NULL
                ORDER BY dr.id ASC
                """
            ),
            {"code": _CODE},
        ).mappings().all()
        row_dicts = [dict(r) for r in rows]
        with_refs = [int(r["id"]) for r in row_dicts if _instance_ref_count(conn, requirement_id=int(r["id"])) > 0]
        canonical_id = min(with_refs) if with_refs else int(row_dicts[0]["id"])
        other_ids = [int(r["id"]) for r in row_dicts if int(r["id"]) != canonical_id]
        for oid in other_ids:
            conn.execute(
                text(
                    """
                    UPDATE document_instances
                    SET selected_requirement_id = :canonical
                    WHERE selected_requirement_id = :old
                    """
                ),
                {"canonical": canonical_id, "old": oid},
            )
            conn.execute(
                text(
                    """
                    UPDATE document_requirements
                    SET is_enabled = 0, frequency = 'HALF_YEARLY'
                    WHERE id = :id AND code = :code
                    """
                ),
                {"id": oid, "code": _CODE},
            )
        conn.execute(
            text(
                """
                UPDATE document_requirements
                SET is_enabled = 1, frequency = 'HALF_YEARLY'
                WHERE id = :id AND code = :code
                """
            ),
            {"id": canonical_id, "code": _CODE},
        )


def downgrade() -> None:
    """비-canonical 행을 자동으로 복구할 근거가 없어 no-op."""
    pass
