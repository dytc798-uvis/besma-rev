"""Explicit offline additive migration. No startup hook and no existing table rewrite."""
from pathlib import Path
from contextlib import closing
import hashlib,json,sqlite3

def upgrade(database,backup):
    from sqlalchemy.dialects.sqlite import dialect
    from sqlalchemy.schema import CreateTable,CreateIndex
    from app.modules.users import models as user_models
    from app.modules.functional_eval import models as evaluation_models
    from app.modules.functional_eval.models import FunctionalEvalAdditionalApproval,FunctionalEvalTargetEnrollment,FunctionalEvalPeriodMode,FunctionalEvalIntakeReceipt
    tables=[FunctionalEvalAdditionalApproval.__table__,FunctionalEvalTargetEnrollment.__table__,FunctionalEvalPeriodMode.__table__,FunctionalEvalIntakeReceipt.__table__]
    database=Path(database).resolve();backup=Path(backup).resolve()
    if not database.is_file()or backup.exists()or database==backup:raise ValueError('EXACT_OFFLINE_DATABASE_AND_FRESH_BACKUP_REQUIRED')
    for path in [database,*database.parents,backup,*backup.parents]:
        if path.exists()and(path.is_symlink()or getattr(path.lstat(),'st_file_attributes',0)&0x400):raise ValueError('REPARSE_MIGRATION_FORBIDDEN')
    quote=lambda value:'"'+value.replace('"','""')+'"'
    def observed(db,names):
        values={}
        for name in names:
            digest=hashlib.sha256();count=0
            columns=[row[1] for row in db.execute('PRAGMA table_info('+quote(name)+')')]
            for row in db.execute('SELECT * FROM '+quote(name)+' ORDER BY '+','.join(quote(column)for column in columns)):
                digest.update(json.dumps(row,default=lambda value:{'bytes_sha256':hashlib.sha256(value).hexdigest()},ensure_ascii=False,separators=(',',':')).encode());count+=1
            values[name]={'rows':count,'sha256':digest.hexdigest()}
        return values
    with closing(sqlite3.connect(database,timeout=0))as db:
        db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN IMMEDIATE')
        try:
            names=[r[0]for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            if any(t.name in names for t in tables):raise ValueError('MIGRATION_ALREADY_OR_PARTIALLY_APPLIED')
            # Refuse the wrong SQLite file or an incompatible legacy schema before
            # making a backup or adding tables. Never repair old tables here.
            required=[t for t in evaluation_models.Base.metadata.tables.values()
                      if t.name.startswith('functional_eval_') and not t.info.get('explicit_migration_only')]
            required.append(user_models.User.__table__)
            for table in required:
                if table.name not in names:raise ValueError('LEGACY_EVALUATION_SCHEMA_REQUIRED')
                columns={row[1] for row in db.execute('PRAGMA table_info('+quote(table.name)+')')}
                if not {column.name for column in table.columns}<=columns:raise ValueError('LEGACY_EVALUATION_COLUMNS_REQUIRED')
            if list(db.execute('PRAGMA foreign_key_check')):raise ValueError('EXISTING_FOREIGN_KEY_CHECK_FAILED')
            before=observed(db,names);schema=list(db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))
            backup.parent.mkdir(parents=True,exist_ok=True)
            with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True))as source,closing(sqlite3.connect(backup))as destination:
                source.backup(destination)
                if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or observed(destination,names)!=before:raise RuntimeError('BACKUP_VERIFICATION_FAILED')
            backup_sha=hashlib.sha256(backup.read_bytes()).hexdigest()
            for table in tables:
                db.execute(str(CreateTable(table).compile(dialect=dialect())))
                for index in table.indexes:db.execute(str(CreateIndex(index).compile(dialect=dialect())))
            if observed(db,names)!=before:raise RuntimeError('EXISTING_ROWS_CHANGED')
            after_schema=[r for r in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")if r[2]in names]
            if after_schema!=schema:raise RuntimeError('EXISTING_SCHEMA_CHANGED')
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok'or list(db.execute('PRAGMA foreign_key_check')):raise RuntimeError('MIGRATION_INTEGRITY_FAILED')
            db.commit();return {'changed':True,'new_tables':[t.name for t in tables],'existing_tables_preserved':len(names),'existing_state_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),'backup_sha256':backup_sha,'existing_rows_deleted':0,'existing_tables_rewritten':0,'activation_performed':False}
        except BaseException:db.rollback();raise
