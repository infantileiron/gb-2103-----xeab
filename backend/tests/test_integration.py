"""端到端接线验证：真实 worker 消费循环、旧库迁移、seed 脚本、inline 模式。"""
import sqlite3
from datetime import datetime,timezone,timedelta

from src.utils.database import query,decode,initialize
from src.utils.identifiers import new_id,now
from src.utils import queue
from src.config import settings
from src.services import runs
from src.services.runs import execute_run,recover_stuck_runs,claim_run


def _insert_run(study_id,status="queued"):
    run_id=new_id()
    query(
        "INSERT INTO runs (id,study_id,status,result_json,error,created_at,attempt,lease_owner,leased_at)"
        " VALUES (?,?,?,?,?,?,0,NULL,NULL)",
        (run_id,study_id,status,None,None,now()),
    )
    return run_id

def _expired_lease():
    return (datetime.now(timezone.utc)-timedelta(seconds=settings.RUN_LEASE_SECONDS+60)).isoformat()


def test_worker_blpop_loop_with_real_crash_and_recovery(app_env,study_id):
    """模拟真实 worker：BLPOP 取消息→认领→崩溃；恢复线程重投→新 worker 完成。"""
    redis=app_env["redis"]
    run_id=_insert_run(study_id,"queued")
    redis.rpush(runs.QUEUE,run_id)
    # worker-A 的一次 BLPOP 迭代（取到消息），随后“进程被 kill”：只认领不计算
    item=redis.blpop(runs.QUEUE,timeout=1)
    assert item is not None
    claim=claim_run(run_id,"worker-A")
    assert claim["attempt"]==1
    # 进程已退出：心跳停止，租约过期；队列里没有消息
    query("UPDATE runs SET leased_at=? WHERE id=?",(_expired_lease(),run_id))
    assert redis.llen(runs.QUEUE)==0
    # 新 worker 启动时的恢复扫描 + 正常 BLPOP 迭代
    assert recover_stuck_runs(redis)==[run_id]
    item=redis.blpop(runs.QUEUE,timeout=1)
    assert item[1].decode()==run_id
    assert execute_run(item[1].decode(),worker_id="worker-B") is True
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="completed" and row["attempt"]==2
    assert redis.llen(runs.QUEUE)==0
    # 恢复线程对健康库反复扫描应是空操作、不产生重复消息
    assert recover_stuck_runs(redis)==[]
    assert redis.llen(runs.QUEUE)==0


def test_legacy_database_gets_recovery_columns(app_env,study_id):
    """旧版本数据库（无 attempt/lease 字段）重启后自动补列且数据完好。"""
    db_path=app_env["db_path"]
    legacy_id=new_id()
    # 先读出完整的研究与数据集，再按旧结构重建
    from src.utils.database import connection as _conn
    with _conn() as _db:
        study_row=dict(_db.execute("SELECT * FROM studies WHERE id=?",(study_id,)).fetchone())
        dataset_row=dict(_db.execute("SELECT * FROM datasets WHERE id=?",(study_row["dataset_id"],)).fetchone())
    # 从零构建一个旧结构数据库（runs 缺少 attempt/lease_owner/leased_at 三列）
    db_path.unlink()
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE datasets (id TEXT PRIMARY KEY, name TEXT, filename TEXT,"
            " rows_json TEXT, created_at TEXT)"
        )
        db.execute(
            "CREATE TABLE studies (id TEXT PRIMARY KEY, name TEXT, dataset_id TEXT,"
            " features_json TEXT, min_k INTEGER, max_k INTEGER, bootstrap INTEGER,"
            " seed INTEGER, created_at TEXT)"
        )
        db.execute(
            "CREATE TABLE runs (id TEXT PRIMARY KEY, study_id TEXT NOT NULL,"
            " status TEXT NOT NULL, result_json TEXT, error TEXT, created_at TEXT NOT NULL)"
        )
        db.execute("INSERT INTO datasets VALUES (?,?,?,?,?)",
                   (dataset_row["id"],dataset_row["name"],dataset_row["filename"],
                    dataset_row["rows_json"],dataset_row["created_at"]))
        db.execute("INSERT INTO studies VALUES (?,?,?,?,?,?,?,?,?)",
                   (study_row["id"],study_row["name"],study_row["dataset_id"],
                    study_row["features_json"],study_row["min_k"],study_row["max_k"],
                    study_row["bootstrap"],study_row["seed"],study_row["created_at"]))
        db.execute(
            "INSERT INTO runs (id,study_id,status,result_json,error,created_at)"
            " VALUES (?,?,?,?,?,?)",
            (legacy_id,study_id,"running",None,None,now()),
        )
        db.commit()
    initialize()  # 触发补列迁移
    with sqlite3.connect(db_path) as db:
        cols=[r[1] for r in db.execute("PRAGMA table_info(runs)").fetchall()]
    assert {"attempt","lease_owner","leased_at"}.issubset(cols)
    row=decode(query("SELECT * FROM runs WHERE id=?",(legacy_id,),one=True))
    assert row["status"]=="running" and row["attempt"]==0 and row["lease_owner"] is None
    # 迁移后的旧卡死任务可被正常认领并完成
    query("UPDATE runs SET leased_at=? WHERE id=?",(_expired_lease(),legacy_id))
    assert execute_run(legacy_id,worker_id="worker-migrated") is True
    assert decode(query("SELECT status FROM runs WHERE id=?",(legacy_id,),one=True))["status"]=="completed"


def test_seed_demo_runs_and_is_repeatable(app_env,monkeypatch):
    monkeypatch.setenv("SEED_DEMO","true")
    import importlib
    from scripts import seed_demo
    importlib.reload(seed_demo)
    counts1=seed_demo.seed()
    assert counts1["runs"]==2 and counts1["profiles"]>0
    # 重复 seed 不产生重复运行/类型（自然键幂等）
    counts2=seed_demo.seed()
    assert counts2==counts1
    seeded=query("SELECT status,attempt FROM runs")
    assert all(r["status"]=="completed" for r in seeded)
    archived=query("SELECT id FROM reports WHERE status='archived'")
    assert len(archived)==1


def test_inline_mode_executes_synchronously(app_env,study_id,monkeypatch):
    monkeypatch.setattr(queue,"TASK_MODE","inline")
    from src.services import runs as runs_svc
    # 直接走服务层 create_run（inline 分支同步执行，不接触 redis）
    created=runs_svc.create_run(study_id)
    assert created["status"]=="completed" and created["attempt"]==1
    assert app_env["redis"].llen(runs.QUEUE)==0
    profiles=query("SELECT COUNT(*) AS c FROM profiles WHERE run_id=?",(created["id"],),one=True)
    assert profiles["c"]==len(created["result"]["profiles"])


def test_worker_module_imports_and_healthcheck_artifacts(app_env):
    # worker 模块可正常导入（main 不启动循环）
    import src.worker as worker
    assert hasattr(worker,"main")
    # 队列常量与服务层一致
    assert worker.QUEUE==runs.QUEUE
