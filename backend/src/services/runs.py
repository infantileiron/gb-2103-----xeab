import json,logging,threading
from datetime import datetime,timezone,timedelta
from pathlib import Path
from fastapi import HTTPException
from src.utils.database import query,connection,decode,PH
from src.utils.identifiers import new_id,now
from src.services.studies import get_study
from src.services.datasets import get_dataset
from src.services.algorithms import analyze
from src.utils.queue import enqueue,QUEUE
from src.models.run import ClusterRun
from src.constants.enums import RunStatus
from src.config import settings
from src.config.settings import (
    ARTIFACT_DIR,
    RECOVERY_INTERVAL_SECONDS,WORKER_ID,
)

ACTIVE=("queued","running")
logger=logging.getLogger("estuary.runs")

def _ts(): return datetime.now(timezone.utc)
def _iso(moment): return moment.isoformat()
def _lease_cutoff(): return _iso(_ts()-timedelta(seconds=settings.RUN_LEASE_SECONDS))

def list_runs(): return [decode(r) for r in query("SELECT * FROM runs ORDER BY created_at DESC")]
def get_run(id):
    row=decode(query("SELECT * FROM runs WHERE id=?",(id,),one=True))
    if row is None: raise HTTPException(404,"运行不存在")
    return row

def create_run(study_id):
    get_study(study_id)
    active=query("SELECT id FROM runs WHERE status IN ('queued','running')")
    if len(active)>=5: raise HTTPException(429,"已有5个任务排队，请稍后重试")
    entity=ClusterRun(new_id(),study_id,RunStatus.queued)
    query(
        "INSERT INTO runs (id,study_id,status,result_json,error,created_at,attempt,lease_owner,leased_at)"
        " VALUES (?,?,?,?,?, ?,0,NULL,NULL)",
        (entity.id,entity.study_id,entity.status.value,None,None,now()),
    )
    try: enqueue(entity.id)
    except Exception as exc:
        query("UPDATE runs SET status='failed',error=? WHERE id=? AND status='queued'",
              ("队列暂不可用，请检查Redis后重试",entity.id))
        raise HTTPException(503,"任务未能入队；恢复队列后可重新运行") from exc
    return get_run(entity.id)

def _fetch(db,run_id):
    row=db.execute(f"SELECT * FROM runs WHERE id={PH}",(run_id,)).fetchone()
    return dict(row) if row else None

def claim_run(run_id,worker_id):
    """原子认领一个可执行的运行。

    可认领：queued、failed（重新投递后的重试）、或租约已过期的 running（worker 中途退出）。
    已 completed 的运行永不重新执行；被健康 worker 持有的 running 不会被抢走。
    返回认领后的行（含新的 attempt），无需执行时返回 None。
    """
    cutoff=_lease_cutoff()
    with connection() as db:
        row=_fetch(db,run_id)
        if row is None: return None
        if row["status"]=="completed": return None
        if row["attempt"]>=settings.RUN_MAX_ATTEMPTS:
            # 达到重试上限的卡住任务落为 failed，等待人工介入（不覆盖已完成行）
            if row["status"] in ACTIVE:
                db.execute(
                    f"UPDATE runs SET status='failed',error={PH},lease_owner=NULL,leased_at=NULL"
                    f" WHERE id={PH} AND status IN ('queued','running')",
                    (f"已重试{settings.RUN_MAX_ATTEMPTS}次仍未完成，请检查数据源后新建运行",run_id),
                )
            return None
        cur=db.execute(
            f"UPDATE runs SET status='running',lease_owner={PH},leased_at={PH},"
            f"attempt=attempt+1,error=NULL"
            f" WHERE (id={PH} AND status IN ('queued','failed'))"
            f" OR (id={PH} AND status='running' AND (leased_at IS NULL OR leased_at<{PH}))",
            (worker_id,_iso(_ts()),run_id,run_id,cutoff),
        )
        if cur.rowcount==0: return None
        return _fetch(db,run_id)

def _heartbeat(run_id,worker_id,attempt,stop_event,lost_event):
    """续租：只要本行仍归本 attempt 所有就刷新 leased_at，否则说明已被击剑淘汰。"""
    while not stop_event.wait(max(1.0,settings.RUN_LEASE_SECONDS/3)):
        try:
            with connection() as db:
                cur=db.execute(
                    f"UPDATE runs SET leased_at={PH} WHERE id={PH} AND lease_owner={PH} AND attempt={PH}",
                    (_iso(_ts()),run_id,worker_id,attempt),
                )
                if cur.rowcount==0:
                    lost_event.set(); return
        except Exception:
            logger.exception("run_heartbeat_failed",extra={"run_id":run_id})

def _write_artifact(run_id,payload):
    output=Path(ARTIFACT_DIR)/"runs"
    output.mkdir(parents=True,exist_ok=True)
    target=output/(run_id+".json")
    temporary=output/(run_id+".tmp")
    temporary.write_text(payload,encoding="utf-8")
    if target.exists():
        # 已有完成的成果文件（更新一次的尝试已落盘），陈旧计算不得覆盖
        temporary.unlink()
    else:
        temporary.replace(target)

def finalize_run(run_id,worker_id,attempt,result):
    """带击剑校验的条件提交：仅本 attempt 仍持有租约、且运行未完成时可写入。"""
    payload=json.dumps(result,ensure_ascii=False)
    with connection() as db:
        row=_fetch(db,run_id)
        if row is None or row["status"]=="completed": return False
        if row["attempt"]!=attempt or row["lease_owner"]!=worker_id: return False
        for p in result["profiles"]:
            db.execute(
                "INSERT INTO profiles (id,run_id,cluster_id,name,notes,centroid_json,size)"
                " VALUES (?,?,?,?,?,?,?) ON CONFLICT (run_id,cluster_id) DO NOTHING",
                (new_id(),run_id,p["cluster_id"],p["name"],"",json.dumps(p["centroid"]),p["size"]),
            )
        cur=db.execute(
            f"UPDATE runs SET status='completed',result_json={PH},error=NULL,"
            f"lease_owner=NULL,leased_at=NULL WHERE id={PH} AND status='running'"
            f" AND attempt={PH} AND lease_owner={PH}",
            (payload,run_id,attempt,worker_id),
        )
        if cur.rowcount==0: return False
    _write_artifact(run_id,payload)
    return True

def fail_run(run_id,worker_id,attempt,message):
    """条件失败落库：不能覆盖更新一次尝试或已完成运行的状态。"""
    with connection() as db:
        cur=db.execute(
            f"UPDATE runs SET status='failed',error={PH},lease_owner=NULL,leased_at=NULL"
            f" WHERE id={PH} AND status='running' AND attempt={PH} AND lease_owner={PH}",
            (message[:500],run_id,attempt,worker_id),
        )
        return cur.rowcount==1

def execute_run(run_id,worker_id=None):
    worker_id=worker_id or WORKER_ID
    claim=claim_run(run_id,worker_id)
    if claim is None:
        logger.info("run_claim_skipped",extra={"run_id":run_id})
        return False
    attempt=claim["attempt"]
    stop_event=threading.Event(); lost_event=threading.Event()
    beat=threading.Thread(
        target=_heartbeat,args=(run_id,worker_id,attempt,stop_event,lost_event),
        name=f"hb-{run_id[:8]}",daemon=True,
    )
    beat.start()
    try:
        study=get_study(claim["study_id"]); dataset=get_dataset(study["dataset_id"])
        result=analyze(dataset["rows"],study["features"],study["min_k"],study["max_k"],study["bootstrap"],study["seed"])
        if lost_event.is_set():
            logger.warning("run_lease_lost_before_finalize",extra={"run_id":run_id,"attempt":attempt})
            return False
        if not finalize_run(run_id,worker_id,attempt,result):
            logger.warning("run_finalize_rejected",extra={"run_id":run_id,"attempt":attempt})
            return False
        return True
    except Exception as exc:
        logger.exception("run_execution_failed",extra={"run_id":run_id,"attempt":attempt})
        fail_run(run_id,worker_id,attempt,str(exc))
        return False
    finally:
        stop_event.set()

def recover_stuck_runs(redis_client):
    """扫描中断遗留的运行并重新入队：queued 丢消息、running 租约过期（worker 退出）。

    重复入队是安全的：claim_run 的条件 UPDATE 保证同一运行只有一个执行者，
    重复消息在认领阶段即被跳过，不会产生重复的分型结果或生态类型。
    """
    cutoff=_lease_cutoff()
    requeued=[]
    stuck=query(
        "SELECT * FROM runs WHERE status='queued' OR"
        " (status='running' AND (leased_at IS NULL OR leased_at<?))",
        (cutoff,),
    )
    for row in stuck:
        if row["attempt"]>=settings.RUN_MAX_ATTEMPTS:
            query(
                "UPDATE runs SET status='failed',error=?,lease_owner=NULL,leased_at=NULL"
                " WHERE id=? AND status IN ('queued','running')",
                (f"已重试{settings.RUN_MAX_ATTEMPTS}次仍未完成，请检查数据源后新建运行",row["id"]),
            )
            continue
        try:
            redis_client.rpush(QUEUE,row["id"])
            requeued.append(row["id"])
        except Exception:
            logger.exception("recovery_requeue_failed",extra={"run_id":row["id"]})
    if requeued: logger.warning("runs_requeued_after_recovery",extra={"run_ids":requeued})
    return requeued

def recovery_loop(redis_client,stop_event):
    while not stop_event.wait(RECOVERY_INTERVAL_SECONDS):
        try: recover_stuck_runs(redis_client)
        except Exception: logger.exception("recovery_sweep_failed")
