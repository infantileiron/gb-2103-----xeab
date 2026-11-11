import json, sqlite3
from contextlib import contextmanager
from pathlib import Path
from src.config.settings import DATABASE_URL
def _is_sqlite(): return DATABASE_URL.startswith("sqlite:///")
PH="?" if _is_sqlite() else "%s"
@contextmanager
def connection():
    if _is_sqlite():
        db=sqlite3.connect(DATABASE_URL[10:], timeout=30)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
    else:
        import psycopg
        from psycopg.rows import dict_row
        db=psycopg.connect(DATABASE_URL,row_factory=dict_row)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally: db.close()
def query(sql,params=(),one=False):
    if not _is_sqlite(): sql=sql.replace("?","%s")
    with connection() as db:
        cur=db.execute(sql,params)
        if cur.description:
            rows=[dict(row) for row in cur.fetchall()]
            return (rows[0] if rows else None) if one else rows
    return None
def table_exists(db,table):
    if _is_sqlite():
        row=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
    else:
        row=db.execute("SELECT 1 FROM information_schema.tables WHERE table_name=%s",(table,)).fetchone()
    return row is not None
def column_exists(db,table,column):
    if _is_sqlite():
        rows=db.execute(f"PRAGMA table_info({table})").fetchall()
        return any(dict(r)["name"]==column for r in rows)
    row=db.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",(table,column)).fetchone()
    return row is not None
def _run_script(db,text):
    # sqlite 驱动一次只执行一条语句；postgres(psycopg) 支持整脚本
    statements=[stmt.strip() for stmt in text.split(";") if stmt.strip()]
    for stmt in statements: db.execute(stmt)
def initialize():
    migrations_dir=Path(__file__).parents[2]/"migrations"
    with connection() as db:
        for path in sorted(migrations_dir.glob("*.sql")):
            _run_script(db,path.read_text())
        # 旧版本库的增量补列，保证重启后具备崩溃恢复所需字段
        if table_exists(db,"runs"):
            for column,ddl in (
                ("attempt","INTEGER NOT NULL DEFAULT 0"),
                ("lease_owner","TEXT"),
                ("leased_at","TEXT"),
            ):
                if not column_exists(db,"runs",column):
                    db.execute(f"ALTER TABLE runs ADD COLUMN {column} {ddl}")
def decode(row):
    if row is None: return None
    result=dict(row)
    for key in list(result):
        if key.endswith("_json"):
            result[key[:-5]]=json.loads(result.pop(key)) if result[key] else None
    return result
