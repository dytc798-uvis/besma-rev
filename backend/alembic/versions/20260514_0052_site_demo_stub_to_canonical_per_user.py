"""site01/02/04/05: stub(SITEnnn) → canonical 현장 per-user (site03은 0051에서 처리됨)

Revision ID: 20260514_0052
Revises: 20260514_0051
Create Date: 2026-05-14

정책 (보수적, idempotent)
-------------------------
- 대상 로그인: ``site01``, ``site02``, ``site04``, ``site05`` 만 (``site03`` 제외).
- 사용자의 현재 ``sites.site_code`` 가 ``^SITE\\d{3}$`` 형태(시드 스텁)일 때만 스텁으로 본다.
- 동일 ``site_name`` 클러스터 키(``routes._site_cluster_key`` 와 동일)를 가진 현장 후보 중
  ``(문서 수, 업로드 이력 수)`` 가 가장 큰 현장을 canonical 로 선택한다.
  동률이면 ``site_id`` 가 더 큰 쪽(운영 요청 tie-break).
- **추가 확인(ambiguous)**: 상위 2개 후보의 (문서+이력) 합이 최대값의 85% 이상이면 자동 이전 없음.
- canonical 과 사용자 ``site_id`` 가 이미 같으면 **정상** — 스킵.
- 확정 시: ``users.site_id`` 를 canonical 로 옮기고, 해당 사용자가 스텁에 남긴
  ``documents`` / 연결 ``document_instances`` 만 ``uploaded_by_user_id`` 일치로 이전한다.
  (타인/비데모 업로드 문서는 건드리지 않음.)

Downgrade
---------
테이블 ``_alembic_site_remap_batch_0052`` 에 기록된 행을 역순으로 되돌린 뒤 테이블을 삭제한다.
"""

from __future__ import annotations

import json
import re
from typing import Any

from alembic import op
from sqlalchemy import text

revision = "20260514_0052"
down_revision = "20260514_0051"
branch_labels = None
depends_on = None

_DEMO_LOGINS = ("site01", "site02", "site04", "site05")
_STUB_CODE_RE = re.compile(r"^SITE\d{3}$")


def _site_cluster_key(site_name: str | None) -> str:
    name = (site_name or "").strip()
    name = re.sub(r"\(삼성인정제\)", "", name)
    name = re.sub(r"\s+", "", name)
    return name.lower()


def _is_stub_site_code(site_code: str | None) -> bool:
    return bool(site_code and _STUB_CODE_RE.match(str(site_code).strip()))


def _fetch_sites(conn) -> list[dict[str, Any]]:
    rows = conn.execute(text("SELECT id, site_code, site_name FROM sites")).mappings().all()
    return [dict(r) for r in rows]


def _counts_by_site(conn) -> tuple[dict[int, int], dict[int, int]]:
    doc_rows = conn.execute(
        text("SELECT site_id, COUNT(*) AS c FROM documents WHERE site_id IS NOT NULL GROUP BY site_id")
    ).all()
    doc_map = {int(r[0]): int(r[1]) for r in doc_rows if r[0] is not None}
    hist_rows = conn.execute(
        text(
            """
            SELECT d.site_id, COUNT(*) AS c
            FROM document_upload_histories h
            JOIN documents d ON d.id = h.document_id
            WHERE d.site_id IS NOT NULL
            GROUP BY d.site_id
            """
        )
    ).all()
    hist_map = {int(r[0]): int(r[1]) for r in hist_rows if r[0] is not None}
    return doc_map, hist_map


def _pick_canonical(
    sites: list[dict[str, Any]],
    *,
    cluster_key: str,
    doc_map: dict[int, int],
    hist_map: dict[int, int],
) -> tuple[int | None, bool]:
    """Returns (canonical_site_id, ambiguous)."""
    peers = [s for s in sites if _site_cluster_key(s.get("site_name")) == cluster_key]
    if not peers:
        return None, False
    # (total, stub_penalty, -doc, -hist, -site_id) — 데이터 많은 쪽, 비스텁 site_code 우선
    scored: list[tuple[int, int, int, int, int]] = []
    for s in peers:
        sid = int(s["id"])
        dc = int(doc_map.get(sid, 0))
        hc = int(hist_map.get(sid, 0))
        total = dc + hc
        stub_pen = 1 if _is_stub_site_code(s.get("site_code")) else 0
        scored.append((total, stub_pen, dc, hc, sid))
    scored.sort(key=lambda t: (-t[0], t[1], -t[2], -t[3], -t[4]))
    if not scored:
        return None, False
    best_w = scored[0][0]
    if best_w <= 0:
        return None, False
    _, _, _, _, best_id = scored[0]
    if len(scored) >= 2:
        w2 = scored[1][0]
        if w2 >= best_w * 0.85:
            return None, True
    return best_id, False


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS _alembic_site_remap_batch_0052 (
                login_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                old_site_id INTEGER NOT NULL,
                new_site_id INTEGER NOT NULL,
                migrated_document_ids TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    sites = _fetch_sites(conn)
    site_by_id = {int(s["id"]): s for s in sites}
    doc_map, hist_map = _counts_by_site(conn)

    for login_id in _DEMO_LOGINS:
        urow = conn.execute(
            text("SELECT id, site_id FROM users WHERE login_id = :lid LIMIT 1"),
            {"lid": login_id},
        ).first()
        if urow is None:
            continue
        user_id = int(urow[0])
        cur_sid = urow[1]
        if cur_sid is None:
            continue
        cur_sid = int(cur_sid)
        cur_site = site_by_id.get(cur_sid)
        if cur_site is None:
            continue
        if not _is_stub_site_code(cur_site.get("site_code")):
            continue
        cluster_key = _site_cluster_key(cur_site.get("site_name"))
        if not cluster_key:
            continue
        canonical_id, ambiguous = _pick_canonical(sites, cluster_key=cluster_key, doc_map=doc_map, hist_map=hist_map)
        if ambiguous or canonical_id is None or canonical_id == cur_sid:
            continue

        user_up = conn.execute(
            text(
                """
                UPDATE users
                SET site_id = :new_sid, updated_at = CURRENT_TIMESTAMP
                WHERE id = :uid AND login_id = :lid AND site_id = :old_sid
                """
            ),
            {"new_sid": canonical_id, "uid": user_id, "lid": login_id, "old_sid": cur_sid},
        )
        rc = getattr(user_up, "rowcount", -1)
        if rc == 0:
            continue

        doc_id_rows = conn.execute(
            text(
                """
                SELECT id FROM documents
                WHERE site_id = :old_sid AND uploaded_by_user_id = :uid
                """
            ),
            {"old_sid": cur_sid, "uid": user_id},
        ).all()
        migrated_ids = [int(r[0]) for r in doc_id_rows if r[0] is not None]
        if migrated_ids:
            conn.execute(
                text(
                    """
                    UPDATE documents
                    SET site_id = :new_sid, updated_at = CURRENT_TIMESTAMP
                    WHERE site_id = :old_sid AND uploaded_by_user_id = :uid
                    """
                ),
                {"new_sid": canonical_id, "old_sid": cur_sid, "uid": user_id},
            )
            conn.execute(
                text(
                    """
                    UPDATE document_instances
                    SET site_id = :new_sid
                    WHERE site_id = :old_sid
                      AND id IN (
                        SELECT instance_id FROM documents
                        WHERE site_id = :new_sid
                          AND uploaded_by_user_id = :uid
                          AND instance_id IS NOT NULL
                      )
                    """
                ),
                {"new_sid": canonical_id, "old_sid": cur_sid, "uid": user_id},
            )

        conn.execute(
            text(
                """
                INSERT INTO _alembic_site_remap_batch_0052
                (login_id, user_id, old_site_id, new_site_id, migrated_document_ids)
                VALUES (:login_id, :user_id, :old_site_id, :new_site_id, :doc_ids)
                """
            ),
            {
                "login_id": login_id,
                "user_id": user_id,
                "old_site_id": cur_sid,
                "new_site_id": canonical_id,
                "doc_ids": json.dumps(migrated_ids),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    try:
        rows = conn.execute(
            text(
                """
                SELECT login_id, user_id, old_site_id, new_site_id, migrated_document_ids
                FROM _alembic_site_remap_batch_0052
                ORDER BY created_at DESC, login_id DESC
                """
            )
        ).mappings().all()
    except Exception:
        return
    for r in rows:
        old_sid = int(r["old_site_id"])
        new_sid = int(r["new_site_id"])
        uid = int(r["user_id"])
        lid = str(r["login_id"])
        raw_ids = r.get("migrated_document_ids")
        migrated_ids: list[int] = []
        if raw_ids:
            try:
                migrated_ids = [int(x) for x in json.loads(str(raw_ids))]
            except (json.JSONDecodeError, TypeError, ValueError):
                migrated_ids = []

        if migrated_ids:
            id_list = ",".join(str(i) for i in migrated_ids)
            conn.execute(
                text(
                    f"""
                    UPDATE document_instances
                    SET site_id = :old_sid
                    WHERE site_id = :new_sid
                      AND id IN (
                        SELECT instance_id FROM documents
                        WHERE id IN ({id_list}) AND instance_id IS NOT NULL
                      )
                    """
                ),
                {"old_sid": old_sid, "new_sid": new_sid},
            )
            conn.execute(
                text(
                    f"""
                    UPDATE documents
                    SET site_id = :old_sid, updated_at = CURRENT_TIMESTAMP
                    WHERE id IN ({id_list}) AND site_id = :new_sid AND uploaded_by_user_id = :uid
                    """
                ),
                {"old_sid": old_sid, "new_sid": new_sid, "uid": uid},
            )

        conn.execute(
            text(
                """
                UPDATE users
                SET site_id = :old_sid, updated_at = CURRENT_TIMESTAMP
                WHERE id = :uid AND login_id = :lid AND site_id = :new_sid
                """
            ),
            {"old_sid": old_sid, "new_sid": new_sid, "uid": uid, "lid": lid},
        )

    conn.execute(text("DROP TABLE IF EXISTS _alembic_site_remap_batch_0052"))
