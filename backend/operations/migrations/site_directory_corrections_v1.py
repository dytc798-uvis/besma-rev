"""Explicit candidate migration; never called from request handlers."""
from pathlib import Path
import sqlite3

SQL=["""CREATE TABLE IF NOT EXISTS site_directory_correction_events (
 site_code TEXT NOT NULL,revision INTEGER NOT NULL,field TEXT NOT NULL CHECK(field IN('address','description','phone','rank')),
 contact_id TEXT NOT NULL,field_label TEXT NOT NULL,value TEXT NOT NULL,before_value TEXT NOT NULL,source_sha256 TEXT NOT NULL,
 request_id TEXT NOT NULL,request_sha256 TEXT NOT NULL,changed_by INTEGER NOT NULL REFERENCES users(id),
 actor_name TEXT NOT NULL,changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(site_code,revision),UNIQUE(changed_by,request_id,field,contact_id))""",
 """CREATE TRIGGER IF NOT EXISTS site_corrections_no_update BEFORE UPDATE ON site_directory_correction_events BEGIN SELECT RAISE(ABORT,'CORRECTION_HISTORY_IMMUTABLE'); END""",
 """CREATE TRIGGER IF NOT EXISTS site_corrections_no_delete BEFORE DELETE ON site_directory_correction_events BEGIN SELECT RAISE(ABORT,'CORRECTION_HISTORY_IMMUTABLE'); END"""]

def upgrade(db_path,backup_path):
 db_path=Path(db_path).resolve();backup_path=Path(backup_path).resolve()
 if not db_path.is_file()or backup_path.exists()or db_path==backup_path:raise ValueError('EXPLICIT_DATABASE_AND_NEW_BACKUP_REQUIRED')
 backup_path.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(db_path)as db,sqlite3.connect(backup_path)as backup:
  db.backup(backup);db.execute('BEGIN IMMEDIATE')
  try:
   for statement in SQL:db.execute(statement)
   db.commit()
  except BaseException:db.rollback();raise
 return {'table':'site_directory_correction_events','backup_created':True,'original_rows_deleted_or_updated':False}
