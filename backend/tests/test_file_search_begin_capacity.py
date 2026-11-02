"""A full metadata store must not acquire another failed empty generation."""
from datetime import datetime, timezone
import hashlib

import pytest

from app.modules.file_search import index_database as storage
from app.modules.file_search.schemas import (
    FileSearchScope, IndexEntry, IndexSessionBeginRequest,
    TEAM_SAFETY_NAS_LOGICAL_ROOT_ID, canonical_entries_bytes,
)


def request(entries=None, *, scope=FileSearchScope.TEAM_SAFETY_NAS, count=None):
    entries = entries if entries is not None else [entry("a")]
    return IndexSessionBeginRequest(
        scope=scope,
        logical_root_id=(TEAM_SAFETY_NAS_LOGICAL_ROOT_ID
                         if scope is FileSearchScope.TEAM_SAFETY_NAS else "b" * 64),
        root_label="Test source", installation_id="a" * 32,
        expected_entry_count=len(entries) if count is None else count,
        expected_sha256=hashlib.sha256(canonical_entries_bytes(entries)).hexdigest(),
        generated_at=datetime.now(timezone.utc),
    )


def entry(name):
    return IndexEntry(relative_path=name, file_name=name, extension="",
                      size=0, modified_at=None, is_directory=False)


@pytest.fixture
def database(tmp_path):
    db = storage.IndexDatabase(tmp_path / "search" / "index.sqlite3")
    db._set_member_for_test(1, can_search=True, can_upload_personal=True,
                            can_publish_nas=True)
    return db


def state(db):
    with db.connection() as c:
        return {name: [tuple(row) for row in c.execute("SELECT * FROM " + name)]
                for name in ["members", "index_sessions", "index_chunks", "index_entries"]}


def publish(db, entries):
    begun = db.begin_session(1, request(entries))
    payload = canonical_entries_bytes(entries)
    db.put_chunk(begun["session_id"], 0, hashlib.sha256(payload).hexdigest(), entries)
    db.commit_session(begun["session_id"])
    return begun


@pytest.mark.parametrize("scope", list(FileSearchScope))
def test_impossible_repeated_begins_preserve_all_history(database, monkeypatch, scope):
    publish(database, [entry("a")])
    publish(database, [entry("b")])
    before = state(database)
    # Match the real remaining budget without importing any production rows.
    existing = sum(row["canonical_bytes"] for row in
                   _sessions(database))
    monkeypatch.setattr(storage, "MAX_DATABASE_CANONICAL_BYTES", existing + 237202)
    for _ in range(30):
        with pytest.raises(storage.IndexDatabaseContractError) as failure:
            database.begin_session(1, request(scope=scope, count=61067))
        assert failure.value.code == "FILE_SEARCH_DATABASE_BYTE_QUOTA"
        assert failure.value.conflict
    assert state(database) == before


def _sessions(db):
    with db.connection() as c:
        return [dict(row) for row in c.execute("SELECT * FROM index_sessions")]


@pytest.mark.parametrize("scope", list(FileSearchScope))
def test_smallest_valid_snapshot_at_exact_capacity_commits(database, monkeypatch, scope):
    entries = [entry("a")]
    payload = canonical_entries_bytes(entries)
    assert len(payload) == storage.MIN_CANONICAL_BYTES_PER_ENTRY == 10
    monkeypatch.setattr(storage, "MAX_DATABASE_CANONICAL_BYTES", len(payload))
    begun = database.begin_session(1, request(entries, scope=scope))
    database.put_chunk(begun["session_id"], 0, hashlib.sha256(payload).hexdigest(), entries)
    database.commit_session(begun["session_id"])
    assert database.session(begun["session_id"])["status"] == "ACTIVE"


def test_active_and_rollback_bytes_count_toward_new_admission(database, monkeypatch):
    publish(database, [entry("a")])
    publish(database, [entry("b")])
    before = state(database)
    assert {r["status"] for r in _sessions(database)} == {"ACTIVE", "RETIRED"}
    monkeypatch.setattr(storage, "MAX_DATABASE_CANONICAL_BYTES", 29)
    with pytest.raises(storage.IndexDatabaseContractError) as failure:
        database.begin_session(1, request([entry("c")]))
    assert failure.value.code == "FILE_SEARCH_DATABASE_BYTE_QUOTA"
    assert state(database) == before


def test_remaining_exact_minimum_with_history_can_still_publish(database, monkeypatch):
    publish(database, [entry("a")])
    publish(database, [entry("b")])
    monkeypatch.setattr(storage, "MAX_DATABASE_CANONICAL_BYTES", 30)
    third = publish(database, [entry("c")])
    assert database.session(third["session_id"])["status"] == "ACTIVE"
    assert sum(r["canonical_bytes"] for r in _sessions(database)) == 30


def test_identical_staging_replay_survives_capacity_change(database, monkeypatch):
    body = request()
    first = database.begin_session(1, body)
    before = state(database)
    monkeypatch.setattr(storage, "MAX_DATABASE_CANONICAL_BYTES", 0)
    assert database.begin_session(1, body) == first
    assert state(database) == before


def test_actual_chunk_bytes_are_still_enforced(database, monkeypatch):
    entries = [entry("long-filename")]
    monkeypatch.setattr(storage, "MAX_DATABASE_CANONICAL_BYTES", 10)
    begun = database.begin_session(1, request(entries))
    before = state(database)
    payload = canonical_entries_bytes(entries)
    assert len(payload) > storage.MIN_CANONICAL_BYTES_PER_ENTRY
    with pytest.raises(storage.IndexDatabaseContractError) as failure:
        database.put_chunk(begun["session_id"], 0, hashlib.sha256(payload).hexdigest(), entries)
    assert failure.value.code == "FILE_SEARCH_DATABASE_BYTE_QUOTA"
    assert state(database) == before


def test_existing_personal_empty_index_contract_is_preserved(database, monkeypatch):
    publish(database, [entry("a")])
    monkeypatch.setattr(storage, "MAX_DATABASE_CANONICAL_BYTES", 10)
    begun = database.begin_session(1, request([], scope=FileSearchScope.PERSONAL))
    assert database.session(begun["session_id"])["expected_entry_count"] == 0
