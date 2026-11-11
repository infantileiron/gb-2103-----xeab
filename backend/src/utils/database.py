import json, sqlite3
from contextlib import contextmanager
from pathlib import Path
from src.config.settings import DATABASE_URL
@contextmanager
def connection():
    if DATABASE_URL.startswith("sqlite:///"):
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
    if not DATABASE_URL.startswith("sqlite:///"): sql=sql.replace("?","%s")
    with connection() as db:
        cur=db.execute(sql,params)
        if cur.description:
            rows=[dict(row) for row in cur.fetchall()]
            return (rows[0] if rows else None) if one else rows
    return None
def initialize():
    text=(Path(__file__).parents[2]/"migrations"/"001_initial.sql").read_text()
    with connection() as db:
        for stmt in text.split(";"):
            if stmt.strip(): db.execute(stmt)
def decode(row):
    if row is None: return None
    result=dict(row)
    for key in list(result):
        if key.endswith("_json"):
            result[key[:-5]]=json.loads(result.pop(key)) if result[key] else None
    return result
