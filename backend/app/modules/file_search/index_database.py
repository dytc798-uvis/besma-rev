from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import stat
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator
from uuid import uuid4

from app.modules.file_search.schemas import (
    MAX_CHUNKS_PER_SESSION,
    TEAM_SAFETY_NAS_DENIED_RELATIVE_PREFIXES,
    TEAM_SAFETY_NAS_LOGICAL_ROOT_ID,
    FileSearchScope,
    FileSearchSort,
    FolderSelector,
    IndexEntry,
    IndexSessionBeginRequest,
    canonical_entries_bytes,
    canonical_entry_line,
    canonical_modified_at,
    search_text_for_entry,
)


SCHEMA_VERSION = 5
MIN_COMMITTED_RETIRED_TO_KEEP_PER_SOURCE = 1
MAX_SEARCH_AUDIT_ROWS = 100_000
MAX_ACTIVE_FILE_SEARCH_MEMBERS = 8
MAX_ACTIVE_PERSONAL_SOURCES_PER_OWNER = 64
MAX_ACTIVE_PERSONAL_ENTRIES_PER_OWNER = 100_000
MAX_ACTIVE_PERSONAL_CANONICAL_BYTES_PER_OWNER = 16 * 1024 * 1024
MAX_STAGING_PERSONAL_ENTRIES_PER_OWNER = 100_000
MAX_STAGING_PERSONAL_CANONICAL_BYTES_PER_OWNER = 16 * 1024 * 1024
# One explicitly retained rollback generation plus the generation superseded by
# the next commit must fit until the reviewed retention CLI runs.
MAX_RETIRED_PERSONAL_ENTRIES_PER_OWNER = 2 * MAX_ACTIVE_PERSONAL_ENTRIES_PER_OWNER
MAX_RETIRED_PERSONAL_CANONICAL_BYTES_PER_OWNER = (
    2 * MAX_ACTIVE_PERSONAL_CANONICAL_BYTES_PER_OWNER
)
MAX_RETIRED_PERSONAL_SESSIONS_PER_OWNER = 128
MAX_SESSIONS_PER_ACTOR = 256
MAX_DATABASE_SESSIONS = 10_000
MAX_DATABASE_ENTRIES = 4_000_000
MAX_PERSONAL_SESSION_CANONICAL_BYTES = 16 * 1024 * 1024
MAX_TEAM_SESSION_CANONICAL_BYTES = 64 * 1024 * 1024
# 8 owners x (16 MiB ACTIVE + 32 MiB RETIRED + 16 MiB STAGING), plus
# three 64 MiB TEAM generations, fit below this hard global ceiling.
MAX_DATABASE_CANONICAL_BYTES = 768 * 1024 * 1024
MAX_DATABASE_AND_WAL_BYTES = 4 * 1024 * 1024 * 1024
MIN_FILESYSTEM_FREE_BYTES = 2 * 1024 * 1024 * 1024
DATABASE_GROWTH_RESERVE_MULTIPLIER = 8
MAX_GENERATED_AT_FUTURE_SKEW_SECONDS = 10 * 60
MAX_FOLDER_CHILDREN = 2_000


class IndexDatabaseContractError(Exception):
    def __init__(self, code: str, *, conflict: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.conflict = conflict


class IndexDatabase:
    """Dedicated derived-index SQLite store; never opens the BESMA business DB."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _prepare_private_runtime_paths(self) -> None:
        if os.name != "posix":
            return
        if not hasattr(os, "O_NOFOLLOW"):
            raise RuntimeError("FILE_SEARCH_PRIVATE_PATH_UNSUPPORTED")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent_stat = os.lstat(self.path.parent)
        if not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != os.geteuid():
            raise RuntimeError("FILE_SEARCH_PRIVATE_DIRECTORY_OWNER")
        os.chmod(self.path.parent, 0o700, follow_symlinks=False)

        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor = os.open(self.path, flags, 0o600)
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != os.geteuid():
                raise RuntimeError("FILE_SEARCH_PRIVATE_DATABASE_OWNER")
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)

    def _secure_existing_sqlite_files(self) -> None:
        if os.name != "posix":
            return
        for path in (
            self.path,
            self.path.with_name(self.path.name + "-wal"),
            self.path.with_name(self.path.name + "-shm"),
            self.path.with_name(self.path.name + "-journal"),
        ):
            if not path.exists():
                continue
            descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                file_stat = os.fstat(descriptor)
                if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != os.geteuid():
                    raise RuntimeError("FILE_SEARCH_PRIVATE_DATABASE_OWNER")
                os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self._prepare_private_runtime_paths()
        if os.name != "posix":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            self._secure_existing_sqlite_files()
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA foreign_keys=ON")
            self.initialize_schema(connection)
            yield connection
        finally:
            connection.close()

    @staticmethod
    def initialize_schema(connection: sqlite3.Connection) -> None:
        current = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise RuntimeError("FILE_SEARCH_SCHEMA_NEWER_THAN_APPLICATION")
        if 0 < current < SCHEMA_VERSION:
            # v1-v4 are undeployed derived-index candidates.  Reusing them
            # would either permit duplicate ACTIVE logical sources or omit the
            # isolated important-file ownership/audit contract introduced in
            # v5, so they must be rebuilt from client/NAS metadata.
            raise RuntimeError("FILE_SEARCH_SCHEMA_REBUILD_REQUIRED")
        if current == SCHEMA_VERSION:
            return
        legacy_session_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='index_sessions'"
        ).fetchone()
        if legacy_session_table is not None and int(
            connection.execute("SELECT COUNT(*) FROM index_sessions").fetchone()[0]
        ):
            raise RuntimeError("FILE_SEARCH_SCHEMA_REBUILD_REQUIRED")
        try:
            connection.executescript(
                """
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS members (
                    user_id INTEGER PRIMARY KEY,
                    provisioned_login_id TEXT,
                    can_search INTEGER NOT NULL DEFAULT 0 CHECK(can_search IN (0,1)),
                    can_upload_personal INTEGER NOT NULL DEFAULT 0 CHECK(can_upload_personal IN (0,1)),
                    can_publish_nas INTEGER NOT NULL DEFAULT 0 CHECK(can_publish_nas IN (0,1)),
                    is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0,1)),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS index_sessions (
                    session_id TEXT PRIMARY KEY,
                    source_key TEXT NOT NULL,
                    scope TEXT NOT NULL CHECK(scope IN ('PERSONAL','TEAM_SAFETY_NAS')),
                    logical_root_id TEXT NOT NULL,
                    root_label TEXT NOT NULL,
                    installation_id TEXT NOT NULL,
                    owner_user_id INTEGER,
                    created_by_user_id INTEGER NOT NULL,
                    expected_entry_count INTEGER NOT NULL CHECK(expected_entry_count >= 0),
                    confirmed_previous_entry_count INTEGER
                        CHECK(confirmed_previous_entry_count >= 0),
                    expected_sha256 TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    canonical_bytes INTEGER NOT NULL DEFAULT 0 CHECK(canonical_bytes >= 0),
                    status TEXT NOT NULL CHECK(status IN ('STAGING','ACTIVE','RETIRED')),
                    created_at TEXT NOT NULL,
                    committed_at TEXT,
                    retired_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_file_search_active_source
                    ON index_sessions(source_key) WHERE status='ACTIVE';
                CREATE INDEX IF NOT EXISTS ix_file_search_session_owner
                    ON index_sessions(scope, owner_user_id, status);
                CREATE TABLE IF NOT EXISTS index_chunks (
                    session_id TEXT NOT NULL,
                    chunk_number INTEGER NOT NULL CHECK(chunk_number >= 0),
                    digest TEXT NOT NULL,
                    entry_count INTEGER NOT NULL,
                    canonical_bytes INTEGER NOT NULL DEFAULT 0 CHECK(canonical_bytes >= 0),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, chunk_number),
                    FOREIGN KEY(session_id) REFERENCES index_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS index_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    chunk_number INTEGER NOT NULL,
                    relative_path TEXT NOT NULL,
                    relative_path_key TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    modified_at TEXT,
                    is_directory INTEGER NOT NULL CHECK(is_directory IN (0,1)),
                    search_text TEXT NOT NULL,
                    UNIQUE(session_id, relative_path_key),
                    FOREIGN KEY(session_id, chunk_number)
                        REFERENCES index_chunks(session_id, chunk_number)
                );
                CREATE INDEX IF NOT EXISTS ix_file_search_entries_session
                    ON index_entries(session_id, relative_path_key);
                CREATE TABLE IF NOT EXISTS important_file_versions (
                    file_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL CHECK(scope IN ('PERSONAL','TEAM_SAFETY_NAS')),
                    logical_root_id TEXT NOT NULL,
                    source_owner_user_id INTEGER NOT NULL CHECK(source_owner_user_id >= 0),
                    source_session_id TEXT NOT NULL,
                    source_installation_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    relative_path_key TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    indexed_size INTEGER NOT NULL CHECK(indexed_size >= 0),
                    indexed_modified_at TEXT,
                    content_size INTEGER NOT NULL CHECK(content_size > 0),
                    content_sha256 TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    storage_key TEXT NOT NULL UNIQUE,
                    owner_user_id INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('ACTIVE','RETIRED')),
                    created_at TEXT NOT NULL,
                    retired_at TEXT,
                    purge_after TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_file_search_important_active_path
                    ON important_file_versions(
                        scope,logical_root_id,source_owner_user_id,relative_path_key
                    ) WHERE status='ACTIVE';
                CREATE INDEX IF NOT EXISTS ix_file_search_important_owner_status
                    ON important_file_versions(owner_user_id,status,created_at);
                CREATE INDEX IF NOT EXISTS ix_file_search_important_purge
                    ON important_file_versions(status,purge_after);
                CREATE TABLE IF NOT EXISTS important_file_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_user_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN (
                        'UPLOAD','UPLOAD_REPLAY','DOWNLOAD','RETIRE','INTEGRITY_FAILURE'
                    )),
                    scope TEXT NOT NULL CHECK(scope IN ('PERSONAL','TEAM_SAFETY_NAS')),
                    content_size INTEGER NOT NULL CHECK(content_size >= 0),
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_file_search_important_audit_file
                    ON important_file_audit(file_id,created_at);
                CREATE TABLE IF NOT EXISTS file_search_access_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_user_id INTEGER NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('FOLDERS','IMPORTANT_LIST')),
                    scope TEXT NOT NULL,
                    result_count INTEGER NOT NULL CHECK(result_count >= 0),
                    duration_ms INTEGER NOT NULL CHECK(duration_ms >= 0),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS search_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_user_id INTEGER NOT NULL,
                    scopes TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    result_count INTEGER NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            member_columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(members)")
            }
            if "provisioned_login_id" not in member_columns:
                # Existing v1 memberships become NULL and therefore fail
                # closed until the explicit provisioning plan is reapplied.
                connection.execute(
                    "ALTER TABLE members ADD COLUMN provisioned_login_id TEXT"
                )
            session_columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(index_sessions)")
            }
            if "canonical_bytes" not in session_columns:
                connection.execute(
                    "ALTER TABLE index_sessions ADD COLUMN canonical_bytes "
                    "INTEGER NOT NULL DEFAULT 0 CHECK(canonical_bytes >= 0)"
                )
            if "confirmed_previous_entry_count" not in session_columns:
                connection.execute(
                    "ALTER TABLE index_sessions ADD COLUMN "
                    "confirmed_previous_entry_count INTEGER "
                    "CHECK(confirmed_previous_entry_count >= 0)"
                )
            chunk_columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(index_chunks)")
            }
            if "canonical_bytes" not in chunk_columns:
                connection.execute(
                    "ALTER TABLE index_chunks ADD COLUMN canonical_bytes "
                    "INTEGER NOT NULL DEFAULT 0 CHECK(canonical_bytes >= 0)"
                )
                connection.execute(
                    "UPDATE index_chunks SET canonical_bytes=COALESCE(("
                    "SELECT SUM("
                    "length(CAST(entry.relative_path AS BLOB))+"
                    "length(CAST(entry.file_name AS BLOB))+"
                    "length(CAST(entry.extension AS BLOB))+"
                    "length(CAST(entry.size AS TEXT))+"
                    "length(CAST(COALESCE(entry.modified_at,'') AS BLOB))+"
                    "length(CAST(entry.is_directory AS TEXT))+6"
                    ") FROM index_entries AS entry "
                    "WHERE entry.session_id=index_chunks.session_id "
                    "AND entry.chunk_number=index_chunks.chunk_number"
                    "),0)"
                )
            connection.execute(
                "UPDATE index_sessions SET canonical_bytes=COALESCE(("
                "SELECT SUM(chunk.canonical_bytes) FROM index_chunks AS chunk "
                "WHERE chunk.session_id=index_sessions.session_id"
                "),0)"
            )
            connection.execute(
                "INSERT INTO schema_meta(key,value) VALUES('schema_version',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    @staticmethod
    def _now() -> str:
        return canonical_modified_at(datetime.now().astimezone())

    def _require_storage_capacity(self, additional_canonical_bytes: int) -> None:
        estimated_growth = max(
            4_096,
            additional_canonical_bytes * DATABASE_GROWTH_RESERVE_MULTIPLIER,
        )
        try:
            current_database_bytes = sum(
                path.stat().st_size
                for path in (
                    self.path,
                    self.path.with_name(self.path.name + "-wal"),
                )
                if path.exists()
            )
            free_bytes = int(shutil.disk_usage(self.path.parent).free)
        except OSError as exception:
            raise IndexDatabaseContractError(
                "FILE_SEARCH_STORAGE_CAPACITY",
                conflict=True,
            ) from exception
        if (
            current_database_bytes + estimated_growth > MAX_DATABASE_AND_WAL_BYTES
            or free_bytes - estimated_growth < MIN_FILESYSTEM_FREE_BYTES
        ):
            raise IndexDatabaseContractError(
                "FILE_SEARCH_STORAGE_CAPACITY",
                conflict=True,
            )

    @staticmethod
    def _source_key(body: IndexSessionBeginRequest, owner_user_id: int | None) -> str:
        identity = (
            [body.scope.value, body.logical_root_id]
            if body.scope is FileSearchScope.TEAM_SAFETY_NAS
            else [body.scope.value, str(owner_user_id), body.logical_root_id]
        )
        return hashlib.sha256("\0".join(identity).encode("utf-8")).hexdigest()

    @staticmethod
    def _require_generated_at_not_in_future(
        generated_at: datetime,
        server_now: str,
    ) -> None:
        parsed_server_now = datetime.fromisoformat(server_now.replace("Z", "+00:00"))
        if generated_at > parsed_server_now + timedelta(
            seconds=MAX_GENERATED_AT_FUTURE_SKEW_SECONDS
        ):
            raise IndexDatabaseContractError("FILE_SEARCH_GENERATED_AT_IN_FUTURE")

    @staticmethod
    def _require_drop_confirmation(
        current_active: sqlite3.Row | None,
        expected_entry_count: int,
        confirmed_previous_entry_count: int | None,
        scope: FileSearchScope,
    ) -> None:
        error_prefix = (
            "FILE_SEARCH_PERSONAL"
            if scope is FileSearchScope.PERSONAL
            else "FILE_SEARCH_TEAM"
        )
        if current_active is None:
            if confirmed_previous_entry_count not in (None, 0):
                raise IndexDatabaseContractError(
                    f"{error_prefix}_ACTIVE_COUNT_CHANGED",
                    conflict=True,
                )
            return
        previous_entry_count = int(current_active["expected_entry_count"])
        if (
            confirmed_previous_entry_count is not None
            and confirmed_previous_entry_count != previous_entry_count
        ):
            raise IndexDatabaseContractError(
                f"{error_prefix}_ACTIVE_COUNT_CHANGED",
                conflict=True,
            )
        is_large_drop = (
            previous_entry_count > 0
            and expected_entry_count < previous_entry_count
            and (previous_entry_count - expected_entry_count) * 100
            > previous_entry_count * 35
        )
        if is_large_drop and confirmed_previous_entry_count is None:
            raise IndexDatabaseContractError(
                f"{error_prefix}_LARGE_DROP_CONFIRMATION_REQUIRED",
                conflict=True,
            )

    @staticmethod
    def _staging_matches_begin_request(
        staging: sqlite3.Row,
        actor_user_id: int,
        body: IndexSessionBeginRequest,
    ) -> bool:
        return (
            int(staging["created_by_user_id"]) == actor_user_id
            and staging["scope"] == body.scope.value
            and staging["logical_root_id"] == body.logical_root_id
            and staging["root_label"] == body.root_label
            and staging["installation_id"] == body.installation_id
            and int(staging["expected_entry_count"]) == body.expected_entry_count
            and staging["expected_sha256"] == body.expected_sha256
            and staging["generated_at"] == canonical_modified_at(body.generated_at)
        )

    @staticmethod
    def _begin_response(session: sqlite3.Row | dict) -> dict:
        return {
            "session_id": session["session_id"],
            "scope": session["scope"],
            "logical_root_id": session["logical_root_id"],
            "installation_id": session["installation_id"],
            "status": "STAGING",
            "expected_entry_count": int(session["expected_entry_count"]),
            "expected_sha256": session["expected_sha256"],
        }

    @staticmethod
    def _team_path_is_denied(relative_path: str) -> bool:
        path_key = relative_path.casefold()
        return any(
            path_key == prefix.casefold()
            or path_key.startswith(prefix.casefold() + "/")
            for prefix in TEAM_SAFETY_NAS_DENIED_RELATIVE_PREFIXES
        )

    @staticmethod
    def _require_personal_source_capacity(
        connection: sqlite3.Connection,
        owner_user_id: int,
        source_key: str,
        expected_entry_count: int,
    ) -> None:
        existing = connection.execute(
            "SELECT expected_entry_count FROM index_sessions WHERE scope='PERSONAL' "
            "AND owner_user_id=? AND source_key=? AND status='ACTIVE'",
            (owner_user_id, source_key),
        ).fetchone()
        active_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM index_sessions WHERE scope='PERSONAL' "
                "AND owner_user_id=? AND status='ACTIVE'",
                (owner_user_id,),
            ).fetchone()[0]
        )
        if existing is None and active_count >= MAX_ACTIVE_PERSONAL_SOURCES_PER_OWNER:
            raise IndexDatabaseContractError(
                "FILE_SEARCH_PERSONAL_SOURCE_LIMIT",
                conflict=True,
            )
        active_expected_total = int(
            connection.execute(
                "SELECT COALESCE(SUM(expected_entry_count),0) FROM index_sessions "
                "WHERE scope='PERSONAL' AND owner_user_id=? AND status='ACTIVE'",
                (owner_user_id,),
            ).fetchone()[0]
        )
        replaced_expected = int(existing["expected_entry_count"]) if existing is not None else 0
        if (
            active_expected_total
            - replaced_expected
            + expected_entry_count
            > MAX_ACTIVE_PERSONAL_ENTRIES_PER_OWNER
        ):
            raise IndexDatabaseContractError(
                "FILE_SEARCH_PERSONAL_ENTRY_QUOTA",
                conflict=True,
            )

    @staticmethod
    def _require_personal_canonical_byte_capacity(
        connection: sqlite3.Connection,
        owner_user_id: int,
        source_key: str,
        session_id: str,
        prospective_staging_bytes: int,
    ) -> None:
        other_active_bytes = int(
            connection.execute(
                "SELECT COALESCE(SUM(canonical_bytes),0) FROM index_sessions "
                "WHERE scope='PERSONAL' AND owner_user_id=? AND status='ACTIVE' "
                "AND source_key<>?",
                (owner_user_id, source_key),
            ).fetchone()[0]
        )
        if (
            other_active_bytes + prospective_staging_bytes
            > MAX_ACTIVE_PERSONAL_CANONICAL_BYTES_PER_OWNER
        ):
            raise IndexDatabaseContractError(
                "FILE_SEARCH_PERSONAL_BYTE_QUOTA",
                conflict=True,
            )
        other_staging_bytes = int(
            connection.execute(
                "SELECT COALESCE(SUM(canonical_bytes),0) FROM index_sessions "
                "WHERE scope='PERSONAL' AND owner_user_id=? AND status='STAGING' "
                "AND session_id<>?",
                (owner_user_id, session_id),
            ).fetchone()[0]
        )
        if (
            other_staging_bytes + prospective_staging_bytes
            > MAX_STAGING_PERSONAL_CANONICAL_BYTES_PER_OWNER
        ):
            raise IndexDatabaseContractError(
                "FILE_SEARCH_PERSONAL_STAGING_BYTE_QUOTA",
                conflict=True,
            )

    @staticmethod
    def _require_personal_staging_entry_capacity(
        connection: sqlite3.Connection,
        owner_user_id: int,
        expected_entry_count: int,
    ) -> None:
        existing_staging_entries = int(
            connection.execute(
                "SELECT COALESCE(SUM(expected_entry_count),0) FROM index_sessions "
                "WHERE scope='PERSONAL' AND owner_user_id=? AND status='STAGING'",
                (owner_user_id,),
            ).fetchone()[0]
        )
        if (
            existing_staging_entries + expected_entry_count
            > MAX_STAGING_PERSONAL_ENTRIES_PER_OWNER
        ):
            raise IndexDatabaseContractError(
                "FILE_SEARCH_PERSONAL_STAGING_ENTRY_QUOTA",
                conflict=True,
            )

    @classmethod
    def _require_retired_transition_capacity(
        cls,
        connection: sqlite3.Connection,
        session_ids: Iterable[str],
    ) -> None:
        candidates = tuple(session_ids)
        if not candidates:
            return
        placeholders = ",".join("?" for _ in candidates)
        rows = connection.execute(
            "SELECT session_id,source_key,scope,owner_user_id,canonical_bytes,committed_at "
            f"FROM index_sessions WHERE session_id IN ({placeholders}) "
            "AND status IN ('ACTIVE','STAGING')",
            candidates,
        ).fetchall()
        personal_owner_ids = {
            int(row["owner_user_id"])
            for row in rows
            if row["scope"] == FileSearchScope.PERSONAL.value
        }
        for owner_user_id in personal_owner_ids:
            owner_candidates = [
                row
                for row in rows
                if row["scope"] == FileSearchScope.PERSONAL.value
                and int(row["owner_user_id"]) == owner_user_id
            ]
            retired_session_count, retired_entry_count, retired_bytes = connection.execute(
                "SELECT COUNT(*),COALESCE(SUM((SELECT COALESCE(SUM(entry_count),0) "
                "FROM index_chunks AS chunks WHERE chunks.session_id=sessions.session_id)),0),"
                "COALESCE(SUM(canonical_bytes),0) FROM index_sessions AS sessions "
                "WHERE scope='PERSONAL' AND owner_user_id=? AND status='RETIRED'",
                (owner_user_id,),
            ).fetchone()
            candidate_entry_count = 0
            for row in owner_candidates:
                candidate_entry_count += int(
                    connection.execute(
                        "SELECT COALESCE(SUM(entry_count),0) FROM index_chunks "
                        "WHERE session_id=?",
                        (row["session_id"],),
                    ).fetchone()[0]
                )
            if (
                int(retired_session_count) + len(owner_candidates)
                > MAX_RETIRED_PERSONAL_SESSIONS_PER_OWNER
                or int(retired_entry_count) + candidate_entry_count
                > MAX_RETIRED_PERSONAL_ENTRIES_PER_OWNER
                or int(retired_bytes)
                + sum(int(row["canonical_bytes"]) for row in owner_candidates)
                > MAX_RETIRED_PERSONAL_CANONICAL_BYTES_PER_OWNER
            ):
                raise IndexDatabaseContractError(
                    "FILE_SEARCH_PERSONAL_RETIRED_QUOTA",
                    conflict=True,
                )

    @staticmethod
    def _require_existing_personal_retired_capacity(
        connection: sqlite3.Connection,
        owner_user_id: int,
    ) -> None:
        retired_session_count, retired_entry_count, retired_bytes = connection.execute(
            "SELECT COUNT(*),COALESCE(SUM((SELECT COALESCE(SUM(entry_count),0) "
            "FROM index_chunks AS chunks WHERE chunks.session_id=sessions.session_id)),0),"
            "COALESCE(SUM(canonical_bytes),0) FROM index_sessions AS sessions "
            "WHERE scope='PERSONAL' AND owner_user_id=? AND status='RETIRED'",
            (owner_user_id,),
        ).fetchone()
        if (
            int(retired_session_count) > MAX_RETIRED_PERSONAL_SESSIONS_PER_OWNER
            or int(retired_entry_count) > MAX_RETIRED_PERSONAL_ENTRIES_PER_OWNER
            or int(retired_bytes) > MAX_RETIRED_PERSONAL_CANONICAL_BYTES_PER_OWNER
        ):
            raise IndexDatabaseContractError(
                "FILE_SEARCH_PERSONAL_RETIRED_QUOTA",
                conflict=True,
            )

    def _set_member_for_test(
        self,
        user_id: int,
        *,
        can_search: bool,
        can_upload_personal: bool,
        can_publish_nas: bool,
        is_active: bool = True,
        provisioned_login_id: str | None = None,
    ) -> None:
        """Test-only fixture helper; production membership uses replace_members exclusively."""

        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO members(
                    user_id,provisioned_login_id,can_search,can_upload_personal,
                    can_publish_nas,is_active,updated_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    provisioned_login_id=excluded.provisioned_login_id,
                    can_search=excluded.can_search,
                    can_upload_personal=excluded.can_upload_personal,
                    can_publish_nas=excluded.can_publish_nas,
                    is_active=excluded.is_active,
                    updated_at=excluded.updated_at
                """,
                (
                    user_id,
                    provisioned_login_id,
                    int(can_search),
                    int(can_upload_personal),
                    int(can_publish_nas),
                    int(is_active),
                    self._now(),
                ),
            )

    def replace_members(
        self,
        members: Iterable[dict],
        *,
        expected_before_snapshot: dict | None = None,
        expected_retirement_impact: dict | None = None,
    ) -> dict:
        """Atomically activate the exact supplied set and deactivate every other member."""

        normalized: list[dict] = []
        seen_user_ids: set[int] = set()
        publisher_count = 0
        for member in members:
            user_id = int(member["user_id"])
            if user_id <= 0 or user_id in seen_user_ids:
                raise ValueError("file-search member user_id values must be unique positive integers")
            seen_user_ids.add(user_id)
            login_id = str(member["login_id"])
            if not login_id or login_id != login_id.strip() or len(login_id) > 255:
                raise ValueError("file-search member login_id values must be non-empty exact strings")
            normalized_member = {
                "user_id": user_id,
                "login_id": login_id,
                "can_search": bool(member["can_search"]),
                "can_upload_personal": bool(member["can_upload_personal"]),
                "can_publish_nas": bool(member["can_publish_nas"]),
            }
            publisher_count += int(normalized_member["can_publish_nas"])
            normalized.append(normalized_member)
        if not normalized:
            raise ValueError("at least one file-search member is required")
        if len(normalized) > MAX_ACTIVE_FILE_SEARCH_MEMBERS:
            raise ValueError(
                f"at most {MAX_ACTIVE_FILE_SEARCH_MEMBERS} active file-search members are allowed"
            )
        if publisher_count != 1:
            raise ValueError("exactly one active NAS publisher is required")
        if any(
            member["can_publish_nas"] and not member["can_search"]
            for member in normalized
        ):
            raise ValueError("the active NAS publisher must also have search permission")
        if any(
            member["can_upload_personal"] and not member["can_search"]
            for member in normalized
        ):
            raise ValueError("personal upload permission requires search permission")
        if any(not member["can_search"] for member in normalized):
            raise ValueError("every active file-search member must have search permission")
        incoming_by_user_id = {
            int(member["user_id"]): member
            for member in normalized
        }
        now = self._now()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current_snapshot = self.provisioning_snapshot()
                if (
                    expected_before_snapshot is not None
                    and current_snapshot != expected_before_snapshot
                ):
                    raise ValueError("reviewed provisioning snapshot changed before apply")
                active_rows = connection.execute(
                    "SELECT user_id FROM members WHERE is_active=1 ORDER BY user_id"
                ).fetchall()
                deactivated_user_ids = [
                    int(row["user_id"])
                    for row in active_rows
                    if int(row["user_id"]) not in seen_user_ids
                ]
                personal_sessions = connection.execute(
                    "SELECT session_id,owner_user_id FROM index_sessions "
                    "WHERE scope='PERSONAL' AND owner_user_id IS NOT NULL "
                    "AND status IN ('ACTIVE','STAGING')"
                ).fetchall()
                current_members = {
                    int(row["user_id"]): row
                    for row in connection.execute(
                        "SELECT user_id,provisioned_login_id,can_publish_nas,is_active "
                        "FROM members"
                    ).fetchall()
                }
                retired_owner_user_ids: set[int] = set()
                retired_session_ids: list[str] = []
                for session in personal_sessions:
                    owner_user_id = int(session["owner_user_id"])
                    incoming = incoming_by_user_id.get(owner_user_id)
                    current = current_members.get(owner_user_id)
                    identity_is_continuous = (
                        incoming is not None
                        and current is not None
                        and bool(current["is_active"])
                        and current["provisioned_login_id"] == incoming["login_id"]
                        and incoming["can_upload_personal"]
                    )
                    if not identity_is_continuous:
                        retired_owner_user_ids.add(owner_user_id)
                        retired_session_ids.append(str(session["session_id"]))
                retired_entry_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM index_entries WHERE session_id IN ("
                        + ",".join("?" for _ in retired_session_ids)
                        + ")"
                        if retired_session_ids
                        else "SELECT 0",
                        retired_session_ids,
                    ).fetchone()[0]
                )
                retired_canonical_bytes = sum(
                    int(session["canonical_bytes"])
                    for session in connection.execute(
                        "SELECT canonical_bytes FROM index_sessions WHERE session_id IN ("
                        + ",".join("?" for _ in retired_session_ids)
                        + ")"
                        if retired_session_ids
                        else "SELECT 0 AS canonical_bytes WHERE 0",
                        retired_session_ids,
                    ).fetchall()
                )
                team_staging_sessions = connection.execute(
                    "SELECT session_id,created_by_user_id,canonical_bytes "
                    "FROM index_sessions WHERE scope='TEAM_SAFETY_NAS' "
                    "AND status='STAGING'"
                ).fetchall()
                retired_team_actor_user_ids: set[int] = set()
                retired_team_session_ids: list[str] = []
                for session in team_staging_sessions:
                    actor_user_id = int(session["created_by_user_id"])
                    incoming = incoming_by_user_id.get(actor_user_id)
                    current = current_members.get(actor_user_id)
                    publishing_identity_is_continuous = (
                        incoming is not None
                        and current is not None
                        and bool(current["is_active"])
                        and current["provisioned_login_id"] == incoming["login_id"]
                        and bool(current["can_publish_nas"])
                        and incoming["can_publish_nas"]
                    )
                    if not publishing_identity_is_continuous:
                        retired_team_actor_user_ids.add(actor_user_id)
                        retired_team_session_ids.append(str(session["session_id"]))
                retired_team_entry_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM index_entries WHERE session_id IN ("
                        + ",".join("?" for _ in retired_team_session_ids)
                        + ")"
                        if retired_team_session_ids
                        else "SELECT 0",
                        retired_team_session_ids,
                    ).fetchone()[0]
                )
                retired_team_canonical_bytes = sum(
                    int(session["canonical_bytes"])
                    for session in team_staging_sessions
                    if str(session["session_id"]) in set(retired_team_session_ids)
                )
                actual_retirement_impact = {
                    "personal": {
                        "owner_user_ids": sorted(retired_owner_user_ids),
                        "owner_count": len(retired_owner_user_ids),
                        "session_count": len(retired_session_ids),
                        "entry_count": retired_entry_count,
                        "canonical_bytes": retired_canonical_bytes,
                    },
                    "team_staging": {
                        "actor_user_ids": sorted(retired_team_actor_user_ids),
                        "actor_count": len(retired_team_actor_user_ids),
                        "session_count": len(retired_team_session_ids),
                        "entry_count": retired_team_entry_count,
                        "canonical_bytes": retired_team_canonical_bytes,
                    },
                }
                if (
                    expected_retirement_impact is not None
                    and actual_retirement_impact != expected_retirement_impact
                ):
                    raise ValueError("reviewed provisioning retirement impact changed before apply")
                if retired_session_ids:
                    connection.executemany(
                        "UPDATE index_sessions SET status='RETIRED',retired_at=? "
                        "WHERE session_id=? AND status IN ('ACTIVE','STAGING')",
                        ((now, session_id) for session_id in retired_session_ids),
                    )
                if retired_team_session_ids:
                    connection.executemany(
                        "UPDATE index_sessions SET status='RETIRED',retired_at=? "
                        "WHERE session_id=? AND status='STAGING'",
                        ((now, session_id) for session_id in retired_team_session_ids),
                    )
                connection.execute(
                    "UPDATE members SET provisioned_login_id=NULL,can_search=0,"
                    "can_upload_personal=0,can_publish_nas=0,is_active=0,updated_at=? "
                    "WHERE is_active=1",
                    (now,),
                )
                connection.executemany(
                    """
                    INSERT INTO members(
                        user_id,provisioned_login_id,can_search,can_upload_personal,
                        can_publish_nas,is_active,updated_at
                    ) VALUES(?,?,?,?,?,1,?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        provisioned_login_id=excluded.provisioned_login_id,
                        can_search=excluded.can_search,
                        can_upload_personal=excluded.can_upload_personal,
                        can_publish_nas=excluded.can_publish_nas,
                        is_active=1,
                        updated_at=excluded.updated_at
                    """,
                    (
                        (
                            member["user_id"],
                            member["login_id"],
                            int(member["can_search"]),
                            int(member["can_upload_personal"]),
                            int(member["can_publish_nas"]),
                            now,
                        )
                        for member in normalized
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {
            "active_member_count": len(normalized),
            "deactivated_user_ids": deactivated_user_ids,
            "retired_owner_user_ids": sorted(retired_owner_user_ids),
            "retired_personal_owner_count": len(retired_owner_user_ids),
            "retired_personal_session_count": len(retired_session_ids),
            "retired_personal_entry_count": retired_entry_count,
            "retired_personal_canonical_bytes": retired_canonical_bytes,
            "retired_team_staging_actor_user_ids": sorted(retired_team_actor_user_ids),
            "retired_team_staging_actor_count": len(retired_team_actor_user_ids),
            "retired_team_staging_session_count": len(retired_team_session_ids),
            "retired_team_staging_entry_count": retired_team_entry_count,
            "retired_team_staging_canonical_bytes": retired_team_canonical_bytes,
        }

    def member(self, user_id: int) -> sqlite3.Row | None:
        with self.connection() as connection:
            return connection.execute(
                "SELECT user_id,provisioned_login_id,can_search,can_upload_personal,"
                "can_publish_nas,is_active "
                "FROM members WHERE user_id=?",
                (user_id,),
            ).fetchone()

    @staticmethod
    def _session_identity_sha256(rows: Iterable[sqlite3.Row]) -> str:
        """Hash generation identities/counts only; no path or filename metadata."""

        digest = hashlib.sha256()
        for row in sorted(rows, key=lambda item: str(item["session_id"]).encode("utf-8")):
            fields = (
                str(row["session_id"]),
                str(row["source_key"]),
                str(row["scope"]),
                str(row["status"]),
                str(row["expected_sha256"]),
                str(int(row["expected_entry_count"])),
                str(int(row["canonical_bytes"])),
            )
            digest.update(("\0".join(fields) + "\n").encode("utf-8"))
        return digest.hexdigest()

    def provisioning_snapshot(self) -> dict:
        """Read membership and destructive apply impact without creating or migrating the DB."""

        if not self.path.is_file():
            return {
                "members": [],
                "personal_owner_count": 0,
                "personal_session_count": 0,
                "personal_entry_count": 0,
                "personal_canonical_bytes": 0,
                "personal_owners": [],
                "team_staging_actors": [],
            }
        uri = f"file:{self.path.resolve(strict=False).as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            table_names = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            members: list[dict] = []
            if "members" in table_names:
                member_columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(members)").fetchall()
                }
                login_expression = (
                    "provisioned_login_id"
                    if "provisioned_login_id" in member_columns
                    else "NULL AS provisioned_login_id"
                )
                members = [
                    {
                        "user_id": int(row["user_id"]),
                        "login_id": row["provisioned_login_id"],
                        "can_search": bool(row["can_search"]),
                        "can_upload_personal": bool(row["can_upload_personal"]),
                        "can_publish_nas": bool(row["can_publish_nas"]),
                        "is_active": bool(row["is_active"]),
                    }
                    for row in connection.execute(
                        f"SELECT user_id,{login_expression},can_search,"
                        "can_upload_personal,can_publish_nas,is_active "
                        "FROM members ORDER BY user_id"
                    ).fetchall()
                ]
            if "index_sessions" not in table_names:
                return {
                    "members": members,
                    "personal_owner_count": 0,
                    "personal_session_count": 0,
                    "personal_entry_count": 0,
                    "personal_canonical_bytes": 0,
                    "personal_owners": [],
                    "team_staging_actors": [],
                }
            session_columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(index_sessions)").fetchall()
            }
            canonical_sum_expression = (
                "COALESCE(SUM(canonical_bytes),0)"
                if "canonical_bytes" in session_columns
                else "0"
            )
            personal_owner_count, personal_session_count, personal_canonical_bytes = connection.execute(
                "SELECT COUNT(DISTINCT owner_user_id),COUNT(*),"
                + canonical_sum_expression
                + " "
                "FROM index_sessions WHERE scope='PERSONAL'"
            ).fetchone()
            personal_entry_count = 0
            if "index_entries" in table_names:
                personal_entry_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM index_entries WHERE session_id IN ("
                        "SELECT session_id FROM index_sessions WHERE scope='PERSONAL'"
                        ")"
                    ).fetchone()[0]
                )
            canonical_column_expression = (
                "canonical_bytes"
                if "canonical_bytes" in session_columns
                else "0 AS canonical_bytes"
            )
            personal_identity_rows: dict[int, list[sqlite3.Row]] = {}
            for row in connection.execute(
                "SELECT owner_user_id,session_id,source_key,scope,status,expected_sha256,"
                "expected_entry_count,"
                + canonical_column_expression
                + " FROM index_sessions WHERE scope='PERSONAL' "
                "ORDER BY owner_user_id,session_id"
            ):
                personal_identity_rows.setdefault(int(row["owner_user_id"]), []).append(row)
            personal_identity_digests = {
                owner_user_id: self._session_identity_sha256(rows)
                for owner_user_id, rows in personal_identity_rows.items()
            }
            personal_owners = [
                {
                    "user_id": int(row["owner_user_id"]),
                    "session_count": int(row["session_count"]),
                    "entry_count": int(row["entry_count"]),
                    "canonical_bytes": int(row["canonical_bytes"]),
                    "session_identity_sha256": personal_identity_digests[
                        int(row["owner_user_id"])
                    ],
                }
                for row in connection.execute(
                    "SELECT sessions.owner_user_id,"
                    "COUNT(DISTINCT sessions.session_id) AS session_count,"
                    "COUNT(entries.entry_id) AS entry_count,"
                    "MAX(owner_totals.canonical_bytes) AS canonical_bytes "
                    "FROM index_sessions AS sessions "
                    "LEFT JOIN index_entries AS entries "
                    "ON entries.session_id=sessions.session_id "
                    "JOIN (SELECT owner_user_id,"
                    + (
                        "SUM(canonical_bytes)"
                        if "canonical_bytes" in session_columns
                        else "0"
                    )
                    + " AS canonical_bytes "
                    "FROM index_sessions WHERE scope='PERSONAL' "
                    "AND status IN ('ACTIVE','STAGING') GROUP BY owner_user_id) "
                    "AS owner_totals ON owner_totals.owner_user_id=sessions.owner_user_id "
                    "WHERE sessions.scope='PERSONAL' "
                    "AND sessions.status IN ('ACTIVE','STAGING') "
                    "GROUP BY sessions.owner_user_id ORDER BY sessions.owner_user_id"
                ).fetchall()
            ]
            team_identity_rows: dict[int, list[sqlite3.Row]] = {}
            for row in connection.execute(
                "SELECT created_by_user_id,session_id,source_key,scope,status,expected_sha256,"
                "expected_entry_count,"
                + canonical_column_expression
                + " FROM index_sessions WHERE scope='TEAM_SAFETY_NAS' "
                "AND status='STAGING' ORDER BY created_by_user_id,session_id"
            ):
                team_identity_rows.setdefault(int(row["created_by_user_id"]), []).append(row)
            team_identity_digests = {
                actor_user_id: self._session_identity_sha256(rows)
                for actor_user_id, rows in team_identity_rows.items()
            }
            team_staging_actors = [
                {
                    "user_id": int(row["created_by_user_id"]),
                    "session_count": int(row["session_count"]),
                    "entry_count": int(row["entry_count"]),
                    "canonical_bytes": int(row["canonical_bytes"]),
                    "session_identity_sha256": team_identity_digests[
                        int(row["created_by_user_id"])
                    ],
                }
                for row in connection.execute(
                    "SELECT sessions.created_by_user_id,COUNT(*) AS session_count,"
                    "COALESCE(SUM((SELECT COUNT(*) FROM index_entries AS entries "
                    "WHERE entries.session_id=sessions.session_id)),0) AS entry_count,"
                    + (
                        "COALESCE(SUM(sessions.canonical_bytes),0)"
                        if "canonical_bytes" in session_columns
                        else "0"
                    )
                    + " AS canonical_bytes FROM index_sessions AS sessions "
                    "WHERE sessions.scope='TEAM_SAFETY_NAS' AND sessions.status='STAGING' "
                    "GROUP BY sessions.created_by_user_id "
                    "ORDER BY sessions.created_by_user_id"
                ).fetchall()
            ]
            return {
                "members": members,
                "personal_owner_count": int(personal_owner_count),
                "personal_session_count": int(personal_session_count),
                "personal_entry_count": personal_entry_count,
                "personal_canonical_bytes": int(personal_canonical_bytes),
                "personal_owners": personal_owners,
                "team_staging_actors": team_staging_actors,
            }
        finally:
            connection.close()

    def begin_session(self, actor_user_id: int, body: IndexSessionBeginRequest) -> dict:
        if (
            body.scope is FileSearchScope.TEAM_SAFETY_NAS
            and body.expected_entry_count < 1
        ):
            raise IndexDatabaseContractError("FILE_SEARCH_TEAM_EMPTY_INDEX")
        owner_user_id = actor_user_id if body.scope is FileSearchScope.PERSONAL else None
        source_key = self._source_key(body, owner_user_id)
        session_id = str(uuid4())
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                server_now = self._now()
                self._require_generated_at_not_in_future(
                    body.generated_at,
                    server_now,
                )
                staging_rows = connection.execute(
                    "SELECT session_id,scope,logical_root_id,root_label,installation_id,"
                    "created_by_user_id,expected_entry_count,expected_sha256,generated_at "
                    "FROM index_sessions WHERE source_key=? AND status='STAGING' "
                    "ORDER BY session_id COLLATE BINARY",
                    (source_key,),
                ).fetchall()
                if staging_rows:
                    if len(staging_rows) == 1 and self._staging_matches_begin_request(
                        staging_rows[0],
                        actor_user_id,
                        body,
                    ):
                        connection.commit()
                        return self._begin_response(staging_rows[0])
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_STAGING_CONFLICT",
                        conflict=True,
                    )
                actor_session_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM index_sessions WHERE created_by_user_id=?",
                        (actor_user_id,),
                    ).fetchone()[0]
                )
                if actor_session_count >= MAX_SESSIONS_PER_ACTOR:
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_SESSION_QUOTA",
                        conflict=True,
                    )
                database_session_count = int(
                    connection.execute("SELECT COUNT(*) FROM index_sessions").fetchone()[0]
                )
                if database_session_count >= MAX_DATABASE_SESSIONS:
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_DATABASE_SESSION_QUOTA",
                        conflict=True,
                    )
                current_active = connection.execute(
                    "SELECT session_id,expected_entry_count FROM index_sessions "
                    "WHERE source_key=? AND status='ACTIVE'",
                    (source_key,),
                ).fetchone()
                self._require_drop_confirmation(
                    current_active,
                    body.expected_entry_count,
                    body.confirmed_previous_entry_count,
                    body.scope,
                )
                if body.scope is FileSearchScope.PERSONAL:
                    self._require_existing_personal_retired_capacity(
                        connection,
                        actor_user_id,
                    )
                    self._require_personal_staging_entry_capacity(
                        connection,
                        actor_user_id,
                        body.expected_entry_count,
                    )
                    self._require_personal_source_capacity(
                        connection,
                        actor_user_id,
                        source_key,
                        body.expected_entry_count,
                    )
                connection.execute(
                    """
                    INSERT INTO index_sessions(
                        session_id,source_key,scope,logical_root_id,root_label,installation_id,
                        owner_user_id,created_by_user_id,expected_entry_count,
                        confirmed_previous_entry_count,expected_sha256,generated_at,status,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'STAGING',?)
                    """,
                    (
                        session_id,
                        source_key,
                        body.scope.value,
                        body.logical_root_id,
                        body.root_label,
                        body.installation_id,
                        owner_user_id,
                        actor_user_id,
                        body.expected_entry_count,
                        body.confirmed_previous_entry_count,
                        body.expected_sha256,
                        canonical_modified_at(body.generated_at),
                        server_now,
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._begin_response(
            {
                "session_id": session_id,
                "scope": body.scope.value,
                "logical_root_id": body.logical_root_id,
                "installation_id": body.installation_id,
                "expected_entry_count": body.expected_entry_count,
                "expected_sha256": body.expected_sha256,
            }
        )

    def session(self, session_id: str) -> sqlite3.Row | None:
        with self.connection() as connection:
            return connection.execute(
                "SELECT * FROM index_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()

    def retire_personal_source(
        self,
        actor_user_id: int,
        logical_root_id: str,
        installation_id: str,
    ) -> dict:
        retired_at = self._now()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "UPDATE index_sessions SET status='RETIRED',retired_at=? "
                    "WHERE logical_root_id=? AND scope='PERSONAL' AND owner_user_id=? "
                    "AND status IN ('ACTIVE','STAGING')",
                    (retired_at, logical_root_id, actor_user_id),
                )
                retired_generation_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM index_sessions WHERE logical_root_id=? "
                        "AND scope='PERSONAL' AND owner_user_id=? AND status='RETIRED'",
                        (logical_root_id, actor_user_id),
                    ).fetchone()[0]
                )
                remaining_active_or_staging_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM index_sessions WHERE logical_root_id=? "
                        "AND scope='PERSONAL' AND owner_user_id=? "
                        "AND status IN ('ACTIVE','STAGING')",
                        (logical_root_id, actor_user_id),
                    ).fetchone()[0]
                )
                if remaining_active_or_staging_count != 0:
                    raise IndexDatabaseContractError("FILE_SEARCH_PERSONAL_RETIRE_INCOMPLETE")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {
            # Always null so never-uploaded, already-retired, active, and
            # staging sources have the same non-oracular response shape.
            "session_id": None,
            "scope": FileSearchScope.PERSONAL.value,
            "logical_root_id": logical_root_id,
            "installation_id": installation_id,
            "status": "RETIRED",
            "retired_at": retired_at,
            "retired_generation_count": retired_generation_count,
            "remaining_active_or_staging_count": remaining_active_or_staging_count,
        }

    def abort_personal_staging(
        self,
        actor_user_id: int,
        logical_root_id: str,
        installation_id: str,
    ) -> dict:
        """Retire only this owner's staging generation for one installation.

        ACTIVE generations and STAGING generations owned by another actor,
        logical source, or installation are intentionally outside this update.
        Keeping the operation idempotent lets a client recover after an upload
        failure without needing to know whether the first abort response arrived.
        """

        retired_at = self._now()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    "UPDATE index_sessions SET status='RETIRED',retired_at=? "
                    "WHERE logical_root_id=? AND scope='PERSONAL' AND owner_user_id=? "
                    "AND installation_id=? AND status='STAGING'",
                    (
                        retired_at,
                        logical_root_id,
                        actor_user_id,
                        installation_id,
                    ),
                )
                retired_staging_generation_count = int(cursor.rowcount)
                remaining_staging_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM index_sessions WHERE logical_root_id=? "
                        "AND scope='PERSONAL' AND owner_user_id=? AND installation_id=? "
                        "AND status='STAGING'",
                        (logical_root_id, actor_user_id, installation_id),
                    ).fetchone()[0]
                )
                if remaining_staging_count != 0:
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_PERSONAL_STAGING_ABORT_INCOMPLETE"
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {
            "scope": FileSearchScope.PERSONAL.value,
            "logical_root_id": logical_root_id,
            "installation_id": installation_id,
            "status": "RETIRED",
            "retired_at": retired_at,
            "retired_staging_generation_count": retired_staging_generation_count,
            "remaining_staging_count": remaining_staging_count,
        }

    def abort_team_staging(
        self,
        actor_user_id: int,
        installation_id: str,
    ) -> dict:
        """Retire only this NAS publisher's STAGING generation."""

        retired_at = self._now()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    "UPDATE index_sessions SET status='RETIRED',retired_at=? "
                    "WHERE logical_root_id=? AND scope='TEAM_SAFETY_NAS' "
                    "AND created_by_user_id=? AND installation_id=? AND status='STAGING'",
                    (
                        retired_at,
                        TEAM_SAFETY_NAS_LOGICAL_ROOT_ID,
                        actor_user_id,
                        installation_id,
                    ),
                )
                retired_staging_generation_count = int(cursor.rowcount)
                remaining_staging_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM index_sessions WHERE logical_root_id=? "
                        "AND scope='TEAM_SAFETY_NAS' AND created_by_user_id=? "
                        "AND installation_id=? AND status='STAGING'",
                        (
                            TEAM_SAFETY_NAS_LOGICAL_ROOT_ID,
                            actor_user_id,
                            installation_id,
                        ),
                    ).fetchone()[0]
                )
                if remaining_staging_count != 0:
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_TEAM_STAGING_ABORT_INCOMPLETE"
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {
            "scope": FileSearchScope.TEAM_SAFETY_NAS.value,
            "logical_root_id": TEAM_SAFETY_NAS_LOGICAL_ROOT_ID,
            "installation_id": installation_id,
            "status": "RETIRED",
            "retired_at": retired_at,
            "retired_staging_generation_count": retired_staging_generation_count,
            "remaining_staging_count": remaining_staging_count,
        }

    def abort_team_staging_session(
        self,
        actor_user_id: int,
        installation_id: str,
        session_id: str,
    ) -> dict:
        """Retire one exact TEAM STAGING generation after a failed publish."""

        retired_at = self._now()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    "UPDATE index_sessions SET status='RETIRED',retired_at=? "
                    "WHERE session_id=? AND logical_root_id=? "
                    "AND scope='TEAM_SAFETY_NAS' AND created_by_user_id=? "
                    "AND installation_id=? AND status='STAGING'",
                    (
                        retired_at,
                        session_id,
                        TEAM_SAFETY_NAS_LOGICAL_ROOT_ID,
                        actor_user_id,
                        installation_id,
                    ),
                )
                retired_staging_generation_count = int(cursor.rowcount)
                remaining_staging_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM index_sessions WHERE session_id=? "
                        "AND logical_root_id=? AND scope='TEAM_SAFETY_NAS' "
                        "AND created_by_user_id=? AND installation_id=? "
                        "AND status='STAGING'",
                        (
                            session_id,
                            TEAM_SAFETY_NAS_LOGICAL_ROOT_ID,
                            actor_user_id,
                            installation_id,
                        ),
                    ).fetchone()[0]
                )
                if remaining_staging_count != 0:
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_TEAM_STAGING_ABORT_INCOMPLETE"
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {
            "session_id": session_id,
            "scope": FileSearchScope.TEAM_SAFETY_NAS.value,
            "logical_root_id": TEAM_SAFETY_NAS_LOGICAL_ROOT_ID,
            "installation_id": installation_id,
            "status": "RETIRED",
            "retired_at": retired_at,
            "retired_staging_generation_count": retired_staging_generation_count,
            "remaining_staging_count": remaining_staging_count,
        }

    def put_chunk(
        self,
        session_id: str,
        chunk_number: int,
        supplied_digest: str,
        entries: list[IndexEntry],
    ) -> dict:
        try:
            canonical_payload = canonical_entries_bytes(entries)
        except ValueError as exception:
            raise IndexDatabaseContractError("FILE_SEARCH_DUPLICATE_RELATIVE_PATH") from exception
        actual_digest = hashlib.sha256(canonical_payload).hexdigest()
        if actual_digest != supplied_digest:
            raise IndexDatabaseContractError("FILE_SEARCH_CHUNK_DIGEST_MISMATCH")

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                session = connection.execute(
                    "SELECT status,scope,source_key,owner_user_id,"
                    "expected_entry_count,canonical_bytes "
                    "FROM index_sessions WHERE session_id=?",
                    (session_id,),
                ).fetchone()
                if session is None:
                    raise IndexDatabaseContractError("FILE_SEARCH_SESSION_NOT_FOUND")
                if session["status"] != "STAGING":
                    raise IndexDatabaseContractError("FILE_SEARCH_SESSION_NOT_STAGING", conflict=True)
                if (
                    session["scope"] == FileSearchScope.TEAM_SAFETY_NAS.value
                    and any(self._team_path_is_denied(entry.relative_path) for entry in entries)
                ):
                    raise IndexDatabaseContractError("FILE_SEARCH_TEAM_PATH_FORBIDDEN")
                expected_entry_count = int(session["expected_entry_count"])
                # Byte-aware clients may need many chunks smaller than the
                # row maximum.  One entry per chunk is the strict useful
                # upper bound, additionally capped against abuse.
                maximum_chunks = min(
                    expected_entry_count,
                    MAX_CHUNKS_PER_SESSION,
                )
                if not 0 <= chunk_number < maximum_chunks:
                    raise IndexDatabaseContractError("FILE_SEARCH_CHUNK_NUMBER_OUT_OF_RANGE")
                existing = connection.execute(
                    "SELECT digest,entry_count,canonical_bytes FROM index_chunks "
                    "WHERE session_id=? AND chunk_number=?",
                    (session_id, chunk_number),
                ).fetchone()
                if existing is not None:
                    if existing["digest"] == actual_digest and existing["entry_count"] == len(entries):
                        connection.rollback()
                        return {
                            "session_id": session_id,
                            "chunk_number": chunk_number,
                            "entry_count": len(entries),
                            "canonical_bytes": int(existing["canonical_bytes"]),
                            "sha256": actual_digest,
                            "idempotent_replay": True,
                        }
                    raise IndexDatabaseContractError("FILE_SEARCH_CHUNK_REPLAY_CONFLICT", conflict=True)

                uploaded_entry_count = int(
                    connection.execute(
                        "SELECT COALESCE(SUM(entry_count),0) FROM index_chunks WHERE session_id=?",
                        (session_id,),
                    ).fetchone()[0]
                )
                if uploaded_entry_count + len(entries) > expected_entry_count:
                    raise IndexDatabaseContractError("FILE_SEARCH_ENTRY_COUNT_EXCEEDED")
                canonical_byte_count = len(canonical_payload)
                session_byte_limit = (
                    MAX_PERSONAL_SESSION_CANONICAL_BYTES
                    if session["scope"] == FileSearchScope.PERSONAL.value
                    else MAX_TEAM_SESSION_CANONICAL_BYTES
                )
                if int(session["canonical_bytes"]) + canonical_byte_count > session_byte_limit:
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_SESSION_BYTE_QUOTA",
                        conflict=True,
                    )
                if session["scope"] == FileSearchScope.PERSONAL.value:
                    self._require_personal_canonical_byte_capacity(
                        connection,
                        int(session["owner_user_id"]),
                        str(session["source_key"]),
                        session_id,
                        int(session["canonical_bytes"]) + canonical_byte_count,
                    )
                database_canonical_bytes = int(
                    connection.execute(
                        "SELECT COALESCE(SUM(canonical_bytes),0) FROM index_sessions"
                    ).fetchone()[0]
                )
                if (
                    database_canonical_bytes + canonical_byte_count
                    > MAX_DATABASE_CANONICAL_BYTES
                ):
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_DATABASE_BYTE_QUOTA",
                        conflict=True,
                    )
                database_entry_count = int(
                    connection.execute(
                        "SELECT COALESCE(SUM(entry_count),0) FROM index_chunks"
                    ).fetchone()[0]
                )
                if database_entry_count + len(entries) > MAX_DATABASE_ENTRIES:
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_DATABASE_ENTRY_QUOTA",
                        conflict=True,
                    )
                self._require_storage_capacity(canonical_byte_count)

                connection.execute(
                    "INSERT INTO index_chunks("
                    "session_id,chunk_number,digest,entry_count,canonical_bytes,created_at"
                    ") VALUES(?,?,?,?,?,?)",
                    (
                        session_id,
                        chunk_number,
                        actual_digest,
                        len(entries),
                        canonical_byte_count,
                        self._now(),
                    ),
                )
                try:
                    connection.executemany(
                        """
                        INSERT INTO index_entries(
                            session_id,chunk_number,relative_path,relative_path_key,file_name,
                            extension,size,modified_at,is_directory,search_text
                        ) VALUES(?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            (
                                session_id,
                                chunk_number,
                                entry.relative_path,
                                entry.relative_path.casefold(),
                                entry.file_name,
                                entry.extension,
                                entry.size,
                                canonical_modified_at(entry.modified_at) or None,
                                int(entry.is_directory),
                                search_text_for_entry(entry),
                            )
                            for entry in entries
                        ),
                    )
                except sqlite3.IntegrityError as exception:
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_DUPLICATE_RELATIVE_PATH",
                        conflict=True,
                    ) from exception
                connection.execute(
                    "UPDATE index_sessions SET canonical_bytes=canonical_bytes+? "
                    "WHERE session_id=?",
                    (canonical_byte_count, session_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {
            "session_id": session_id,
            "chunk_number": chunk_number,
            "entry_count": len(entries),
            "canonical_bytes": len(canonical_payload),
            "sha256": actual_digest,
            "idempotent_replay": False,
        }

    @staticmethod
    def _entry_from_row(row: sqlite3.Row) -> IndexEntry:
        return IndexEntry.model_validate(
            {
                "relative_path": row["relative_path"],
                "file_name": row["file_name"],
                "extension": row["extension"],
                "size": row["size"],
                "modified_at": row["modified_at"],
                "is_directory": bool(row["is_directory"]),
            }
        )

    @classmethod
    def _canonical_session_digest(
        cls,
        connection: sqlite3.Connection,
        session_id: str,
    ) -> tuple[int, str]:
        """Hash one generation in SQLite BINARY/UTF-8 order without materializing rows."""

        digest = hashlib.sha256()
        entry_count = 0
        cursor = connection.execute(
            "SELECT relative_path,file_name,extension,size,modified_at,is_directory "
            "FROM index_entries WHERE session_id=? "
            "ORDER BY relative_path COLLATE BINARY",
            (session_id,),
        )
        for row in cursor:
            digest.update(canonical_entry_line(cls._entry_from_row(row)))
            entry_count += 1
        return entry_count, digest.hexdigest()

    def commit_session(self, session_id: str) -> dict:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                session = connection.execute(
                    "SELECT * FROM index_sessions WHERE session_id=?",
                    (session_id,),
                ).fetchone()
                if session is None:
                    raise IndexDatabaseContractError("FILE_SEARCH_SESSION_NOT_FOUND")
                if session["status"] == "ACTIVE":
                    connection.rollback()
                    return self._commit_response(session, idempotent_replay=True)
                if session["status"] != "STAGING":
                    raise IndexDatabaseContractError("FILE_SEARCH_SESSION_NOT_STAGING", conflict=True)

                if session["scope"] == FileSearchScope.PERSONAL.value:
                    self._require_personal_source_capacity(
                        connection,
                        int(session["owner_user_id"]),
                        str(session["source_key"]),
                        int(session["expected_entry_count"]),
                    )
                    self._require_personal_canonical_byte_capacity(
                        connection,
                        int(session["owner_user_id"]),
                        str(session["source_key"]),
                        session_id,
                        int(session["canonical_bytes"]),
                    )

                current_active = connection.execute(
                    "SELECT session_id,generated_at,expected_entry_count "
                    "FROM index_sessions "
                    "WHERE source_key=? AND status='ACTIVE'",
                    (session["source_key"],),
                ).fetchone()
                self._require_drop_confirmation(
                    current_active,
                    int(session["expected_entry_count"]),
                    (
                        int(session["confirmed_previous_entry_count"])
                        if session["confirmed_previous_entry_count"] is not None
                        else None
                    ),
                    FileSearchScope(str(session["scope"])),
                )
                if (
                    current_active is not None
                    and session["generated_at"] <= current_active["generated_at"]
                ):
                    raise IndexDatabaseContractError(
                        "FILE_SEARCH_GENERATION_NOT_NEWER",
                        conflict=True,
                    )
                if current_active is not None:
                    self._require_retired_transition_capacity(
                        connection,
                        (str(current_active["session_id"]),),
                    )

                chunk_numbers = [
                    int(row[0])
                    for row in connection.execute(
                        "SELECT chunk_number FROM index_chunks WHERE session_id=? ORDER BY chunk_number",
                        (session_id,),
                    )
                ]
                if chunk_numbers and chunk_numbers != list(range(len(chunk_numbers))):
                    raise IndexDatabaseContractError("FILE_SEARCH_CHUNKS_NOT_CONTIGUOUS")
                entry_count, actual_sha256 = self._canonical_session_digest(
                    connection,
                    session_id,
                )
                if entry_count != int(session["expected_entry_count"]):
                    raise IndexDatabaseContractError("FILE_SEARCH_ENTRY_COUNT_MISMATCH")
                if actual_sha256 != session["expected_sha256"]:
                    raise IndexDatabaseContractError("FILE_SEARCH_CANONICAL_SHA256_MISMATCH")

                now = self._now()
                connection.execute(
                    "UPDATE index_sessions SET status='RETIRED',retired_at=? "
                    "WHERE source_key=? AND status='ACTIVE' AND session_id<>?",
                    (now, session["source_key"], session_id),
                )
                connection.execute(
                    "UPDATE index_sessions SET status='ACTIVE',committed_at=? WHERE session_id=?",
                    (now, session_id),
                )
                connection.commit()
                active = connection.execute(
                    "SELECT * FROM index_sessions WHERE session_id=?",
                    (session_id,),
                ).fetchone()
                return self._commit_response(active, idempotent_replay=False)
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _commit_response(session: sqlite3.Row, *, idempotent_replay: bool) -> dict:
        return {
            "session_id": session["session_id"],
            "scope": session["scope"],
            "status": session["status"],
            "entry_count": int(session["expected_entry_count"]),
            "canonical_bytes": int(session["canonical_bytes"]),
            "sha256": session["expected_sha256"],
            "generated_at": session["generated_at"],
            "idempotent_replay": idempotent_replay,
        }

    def search(
        self,
        actor_user_id: int,
        scopes: tuple[FileSearchScope, ...],
        included_tokens: tuple[str, ...],
        excluded_tokens: tuple[str, ...],
        extensions: tuple[str, ...],
        folder: FolderSelector | None,
        limit: int,
        sort_mode: FileSearchSort = FileSearchSort.RELEVANCE,
        offset: int = 0,
    ) -> tuple[list[dict], int, int]:
        started = time.perf_counter()
        if type(offset) is not int or not 0 <= offset <= 1_000_000:
            raise IndexDatabaseContractError("FILE_SEARCH_OFFSET_INVALID")
        if not included_tokens and not excluded_tokens and folder is None:
            raise IndexDatabaseContractError("FILE_SEARCH_QUERY_INVALID")
        try:
            normalized_sort = FileSearchSort(sort_mode)
        except (TypeError, ValueError) as exception:
            raise IndexDatabaseContractError("FILE_SEARCH_SORT_INVALID") from exception
        scope_values = tuple(scope.value for scope in scopes)
        where = [
            "s.status='ACTIVE'",
            "s.scope IN (" + ",".join("?" for _ in scope_values) + ")",
            "(s.scope='TEAM_SAFETY_NAS' OR (s.scope='PERSONAL' AND s.owner_user_id=?))",
        ]
        parameters: list[object] = [*scope_values, actor_user_id]
        if folder is not None:
            where.extend(
                (
                    "s.scope=?",
                    "s.logical_root_id=?",
                    "s.installation_id=?",
                )
            )
            parameters.extend(
                (
                    folder.scope.value,
                    folder.logical_root_id,
                    folder.installation_id,
                )
            )
            if folder.relative_path:
                folder_key = folder.relative_path.casefold()
                folder_length = len(folder_key)
                where.append(
                    "(e.relative_path_key=? OR "
                    "(substr(e.relative_path_key,1,?)=? "
                    "AND substr(e.relative_path_key,?+1,1)='/'))"
                )
                parameters.extend(
                    (folder_key, folder_length, folder_key, folder_length)
                )
        if extensions:
            where.append("e.is_directory=0")
            where.append(
                "e.extension IN (" + ",".join("?" for _ in extensions) + ")"
            )
            parameters.extend(extensions)
        for token in included_tokens:
            where.append("instr(e.search_text, ?) > 0")
            parameters.append(token)
        for token in excluded_tokens:
            where.append("instr(e.search_text, ?) = 0")
            parameters.append(token)
        filtered_parameters = tuple(parameters)
        # The original NFC text is retained after the case-insensitive keys so
        # results stay deterministic when names only differ by case.  Source
        # identity is the final tie-break for identical relative paths from
        # otherwise distinct visible sources.
        name_path_order_sql = (
            "e.file_name COLLATE NOCASE,e.file_name COLLATE BINARY,"
            "e.relative_path_key,e.relative_path COLLATE BINARY,"
            "s.scope,s.logical_root_id,s.installation_id"
        )
        if normalized_sort is FileSearchSort.NEWEST:
            order_sql = (
                "CASE WHEN e.modified_at IS NULL OR e.modified_at='' THEN 1 ELSE 0 END,"
                "e.modified_at DESC," + name_path_order_sql
            )
        elif normalized_sort is FileSearchSort.NAME or not included_tokens:
            order_sql = name_path_order_sql
        else:
            order_sql = (
                "CASE WHEN instr(e.file_name, ?) > 0 THEN 0 ELSE 1 END,"
                + name_path_order_sql
            )
            parameters.append(included_tokens[0])
        parameters.extend((limit, offset))
        sql = f"""
            SELECT s.scope,s.logical_root_id,s.root_label,s.installation_id,s.generated_at,
                   e.relative_path,e.file_name,e.extension,e.size,e.modified_at,e.is_directory,
                   CASE WHEN e.is_directory=0 AND mobile.file_id IS NOT NULL
                        THEN 1 ELSE 0 END AS is_important,
                   CASE WHEN e.is_directory=0 AND mobile.file_id IS NOT NULL
                        THEN 1 ELSE 0 END AS mobile_view_available,
                   CASE WHEN e.is_directory=0 THEN mobile.file_id ELSE NULL END
                        AS important_file_id
            FROM index_entries e
            JOIN index_sessions s ON s.session_id=e.session_id
            LEFT JOIN important_file_versions mobile
              ON mobile.status='ACTIVE'
             AND mobile.scope=s.scope
             AND mobile.logical_root_id=s.logical_root_id
             AND mobile.source_owner_user_id=(
                 CASE WHEN s.scope='PERSONAL' THEN s.owner_user_id ELSE 0 END
             )
             AND mobile.relative_path_key=e.relative_path_key
             AND mobile.indexed_size=e.size
             AND COALESCE(mobile.indexed_modified_at,'')=COALESCE(e.modified_at,'')
            WHERE {' AND '.join(where)}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
        """
        with self.connection() as connection:
            total_count = int(connection.execute(
                f"""
                SELECT COUNT(*)
                FROM index_entries e
                JOIN index_sessions s ON s.session_id=e.session_id
                WHERE {' AND '.join(where)}
                """,
                filtered_parameters,
            ).fetchone()[0])
            rows = connection.execute(sql, parameters).fetchall()
            results = [dict(row) for row in rows]
            for result in results:
                result["is_directory"] = bool(result["is_directory"])
                result["is_important"] = bool(result["is_important"])
                result["mobile_view_available"] = bool(
                    result["mobile_view_available"]
                )
            duration_ms = max(0, int((time.perf_counter() - started) * 1_000))
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO search_audit(actor_user_id,scopes,token_count,result_count,duration_ms,created_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        actor_user_id,
                        ",".join(scope_values),
                        len(included_tokens) + len(excluded_tokens),
                        len(results),
                        duration_ms,
                        self._now(),
                    ),
                )
                connection.execute(
                    "DELETE FROM search_audit WHERE audit_id <= COALESCE(("
                    "SELECT audit_id FROM search_audit ORDER BY audit_id DESC LIMIT 1 OFFSET ?"
                    "),0)",
                    (MAX_SEARCH_AUDIT_ROWS,),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return results, total_count, duration_ms

    def folders(
        self,
        actor_user_id: int,
        folder: FolderSelector,
    ) -> tuple[list[dict], int]:
        """Return lazy immediate-child folders for one exact visible ACTIVE source."""

        started = time.perf_counter()
        where = [
            "s.status='ACTIVE'",
            "s.scope=?",
            "s.logical_root_id=?",
            "s.installation_id=?",
            "(s.scope='TEAM_SAFETY_NAS' OR (s.scope='PERSONAL' AND s.owner_user_id=?))",
        ]
        parameters: list[object] = [
            folder.scope.value,
            folder.logical_root_id,
            folder.installation_id,
            actor_user_id,
        ]
        if folder.relative_path:
            folder_key = folder.relative_path.casefold()
            folder_length = len(folder_key)
            where.append(
                "(e.relative_path_key=? OR "
                "(substr(e.relative_path_key,1,?)=? "
                "AND substr(e.relative_path_key,?+1,1)='/'))"
            )
            parameters.extend(
                (folder_key, folder_length, folder_key, folder_length)
            )

        sql = f"""
            SELECT s.scope,s.logical_root_id,s.root_label,s.installation_id,
                   e.relative_path,e.is_directory
            FROM index_entries e
            JOIN index_sessions s ON s.session_id=e.session_id
            WHERE {' AND '.join(where)}
            ORDER BY e.relative_path_key,e.relative_path COLLATE BINARY
        """
        parent_parts = folder.relative_path.split("/") if folder.relative_path else []
        parent_keys = tuple(part.casefold() for part in parent_parts)
        parent_depth = len(parent_parts)
        children: dict[str, dict] = {}

        with self.connection() as connection:
            rows = connection.execute(sql, parameters)
            for row in rows:
                path_parts = str(row["relative_path"]).split("/")
                if (
                    len(path_parts) < parent_depth
                    or tuple(part.casefold() for part in path_parts[:parent_depth])
                    != parent_keys
                ):
                    continue
                is_directory = bool(row["is_directory"])
                directory_parts = path_parts if is_directory else path_parts[:-1]
                if len(directory_parts) <= parent_depth:
                    continue
                child_parts = directory_parts[: parent_depth + 1]
                child_relative_path = "/".join(child_parts)
                child_key = child_relative_path.casefold()
                child = children.get(child_key)
                if child is None:
                    if len(children) >= MAX_FOLDER_CHILDREN:
                        raise IndexDatabaseContractError(
                            "FILE_SEARCH_FOLDER_CHILD_LIMIT",
                            conflict=True,
                        )
                    child = {
                        "scope": str(row["scope"]),
                        "logical_root_id": str(row["logical_root_id"]),
                        "root_label": str(row["root_label"]),
                        "installation_id": str(row["installation_id"]),
                        "relative_path": child_relative_path,
                        "name": child_parts[-1],
                        "has_children": False,
                        "descendant_file_count": 0,
                    }
                    children[child_key] = child
                if len(directory_parts) > parent_depth + 1:
                    child["has_children"] = True
                if not is_directory:
                    child["descendant_file_count"] += 1

        items = sorted(
            children.values(),
            key=lambda item: (
                str(item["name"]).casefold(),
                str(item["relative_path"]).encode("utf-8"),
            ),
        )
        duration_ms = max(0, int((time.perf_counter() - started) * 1_000))
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO file_search_access_audit("
                    "actor_user_id,action,scope,result_count,duration_ms,created_at"
                    ") VALUES(?,'FOLDERS',?,?,?,?)",
                    (
                        actor_user_id,
                        folder.scope.value,
                        len(items),
                        duration_ms,
                        self._now(),
                    ),
                )
                connection.execute(
                    "DELETE FROM file_search_access_audit WHERE audit_id <= COALESCE(("
                    "SELECT audit_id FROM file_search_access_audit "
                    "ORDER BY audit_id DESC LIMIT 1 OFFSET ?),0)",
                    (MAX_SEARCH_AUDIT_ROWS,),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return items, duration_ms

    def state(self, actor_user_id: int) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT s.session_id,s.scope,s.logical_root_id,s.root_label,s.installation_id,
                       s.generated_at,s.committed_at,s.status,
                       s.expected_sha256 AS sha256,s.expected_entry_count AS entry_count,
                       s.canonical_bytes
                FROM index_sessions s
                WHERE s.status='ACTIVE'
                  AND (s.scope='TEAM_SAFETY_NAS' OR (s.scope='PERSONAL' AND s.owner_user_id=?))
                ORDER BY s.scope,s.root_label,s.logical_root_id
                """,
                (actor_user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
