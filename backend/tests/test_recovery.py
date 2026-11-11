"""崩溃恢复与重复投递幂等性验证。

覆盖：
1. 认领后 worker 退出（queued 丢消息 / running 租约过期）→ 恢复后自动续跑
2. 重复投递 → 不重复执行、不重复生成 profiles 与生态类型
3. 恢复期间再次退出 → 第二次恢复仍能完成
4. 已完成/已归档成果不被重试覆盖；失败重试的旧计算不能覆盖新结果
"""
import json,threading,time
from datetime import datetime,timezone,timedelta

from src.utils.database import query,decode
from src.utils.identifiers import new_id,now
from src.config import settings
from src.services import runs
from src.services.runs import (
    claim_run,execute_run,recover_stuck_runs,finalize_run,fail_run,
)


def _insert_run(study_id,status="queued",**kw):
    run_id=new_id()
    query(
        "INSERT INTO runs (id,study_id,status,result_json,error,created_at,attempt,lease_owner,leased_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (run_id,study_id,status,kw.get("result_json"),kw.get("error"),now(),
         kw.get("attempt",0),kw.get("lease_owner"),kw.get("leased_at")),
    )
    return run_id

def _expired_lease():
    return (datetime.now(timezone.utc)-timedelta(seconds=settings.RUN_LEASE_SECONDS+60)).isoformat()

def _fresh_lease():
    return datetime.now(timezone.utc).isoformat()

def _profile_count(run_id):
    return query("SELECT COUNT(*) AS c FROM profiles WHERE run_id=?",(run_id,),one=True)["c"]


# ---------- 场景 1a：queued 任务消息丢失（worker 从未取到）----------
def test_queued_message_lost_is_requeued_and_completed(app_env,study_id):
    run_id=_insert_run(study_id,"queued")
    redis=app_env["redis"]
    assert redis.llen(runs.QUEUE)==0
    # worker 启动时的恢复扫描
    requeued=recover_stuck_runs(redis)
    assert requeued==[run_id]
    assert redis.lpop(runs.QUEUE).decode()==run_id
    # 新 worker 进程继续处理
    assert execute_run(run_id,worker_id="worker-recovered") is True
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="completed"
    assert row["attempt"]==1
    assert row["lease_owner"] is None and row["leased_at"] is None
    assert _profile_count(run_id)>=2
    assert (app_env["artifact"]/"runs"/f"{run_id}.json").exists()


# ---------- 场景 1b：认领后计算中途退出，一直停在 running ----------
def test_running_worker_crash_lease_expiry_resumes(app_env,study_id):
    run_id=_insert_run(study_id,"queued")
    redis=app_env["redis"]
    # worker A 认领后崩溃（直接模拟其数据库认领结果，不跑计算）
    claim=claim_run(run_id,"worker-A")
    assert claim["status"]=="running" and claim["attempt"]==1 and claim["lease_owner"]=="worker-A"
    # 消息已被 BLPOP 取走，队列空了
    assert redis.llen(runs.QUEUE)==0
    # 租约未过期：健康 worker 仍在跑，恢复扫描不应重投
    assert recover_stuck_runs(redis)==[]
    # worker A 进程退出：心跳停止，租约过期
    query("UPDATE runs SET leased_at=? WHERE id=?",(_expired_lease(),run_id))
    requeued=recover_stuck_runs(redis)
    assert requeued==[run_id]
    assert execute_run(run_id,worker_id="worker-B") is True
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="completed" and row["attempt"]==2
    profiles=query("SELECT cluster_id,name,size FROM profiles WHERE run_id=? ORDER BY cluster_id",(run_id,))
    assert len(profiles)>=2 and len({p["cluster_id"] for p in profiles})==len(profiles)
    assert all(p["name"].startswith("生态类型") for p in profiles)


# ---------- 场景 2：重复投递不重复执行、不重复生成结果 ----------
def test_recovery_duplicates_original_message_is_deduped(app_env,study_id):
    """消息还在队列里 worker 就退出：恢复再投一条，队列出现重复消息，仍只执行一次。"""
    run_id=_insert_run(study_id,"queued")
    redis=app_env["redis"]
    # 原始消息未被 BLPOP 取走，恢复扫描又投了一条
    redis.rpush(runs.QUEUE,run_id)
    assert recover_stuck_runs(redis)==[run_id]
    assert redis.llen(runs.QUEUE)==2
    outcomes=[]
    while redis.llen(runs.QUEUE):
        outcomes.append(execute_run(redis.lpop(runs.QUEUE).decode(),worker_id="worker-D"))
    assert outcomes==[True,False]
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="completed" and row["attempt"]==1
    assert _profile_count(run_id)==len(row["result"]["profiles"])


def test_duplicate_deliveries_are_idempotent(app_env,study_id):
    run_id=_insert_run(study_id,"queued")
    redis=app_env["redis"]
    # 同一 run_id 被投递多次（恢复扫描 + 原始消息同时存在）
    for _ in range(3): redis.rpush(runs.QUEUE,run_id)
    results=[]
    while redis.llen(runs.QUEUE):
        results.append(execute_run(redis.lpop(runs.QUEUE).decode(),worker_id="worker-X"))
    assert results==[True,False,False]
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="completed" and row["attempt"]==1
    # profiles 只有一套，没有重复生态类型
    assert _profile_count(run_id)==len(row["result"]["profiles"])
    # 已完成的运行再次收到消息也不会重跑
    redis.rpush(runs.QUEUE,run_id)
    assert execute_run(redis.lpop(runs.QUEUE).decode(),worker_id="worker-late") is False
    assert decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))["attempt"]==1


def test_concurrent_claims_only_one_wins(app_env,study_id):
    run_id=_insert_run(study_id,"queued")
    winners=[]
    lock=threading.Lock()
    def worker(name):
        got=claim_run(run_id,name)
        with lock:
            if got: winners.append((name,got["attempt"]))
    threads=[threading.Thread(target=worker,args=(f"worker-{i}",)) for i in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(winners)==1
    # 其余 worker 的消息处理直接跳过
    assert execute_run(run_id,worker_id="worker-other") is False


# ---------- 场景 3：恢复期间再次退出，第二次恢复仍能完成 ----------
def test_repeated_crashes_then_eventual_completion(app_env,study_id):
    run_id=_insert_run(study_id,"queued")
    redis=app_env["redis"]
    # 第一次：worker-A 认领后崩溃
    claim_run(run_id,"worker-A")
    query("UPDATE runs SET leased_at=? WHERE id=?",(_expired_lease(),run_id))
    recover_stuck_runs(redis)
    # 第二次：worker-B 通过 BLPOP 取走消息并认领后又崩溃
    assert redis.lpop(runs.QUEUE).decode()==run_id
    claim=claim_run(run_id,"worker-B")
    assert claim["attempt"]==2
    query("UPDATE runs SET leased_at=? WHERE id=?",(_expired_lease(),run_id))
    # 此时 running 且消息已被取走
    assert redis.llen(runs.QUEUE)==0
    recover_stuck_runs(redis)
    assert redis.llen(runs.QUEUE)==1
    # 第三次：worker-C 完成
    assert execute_run(redis.lpop(runs.QUEUE).decode(),worker_id="worker-C") is True
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="completed" and row["attempt"]==3
    assert _profile_count(run_id)==len(row["result"]["profiles"])


def test_attempts_exhausted_marks_failed(app_env,study_id,monkeypatch):
    monkeypatch.setattr(settings,"RUN_MAX_ATTEMPTS",2)
    run_id=_insert_run(study_id,"queued",attempt=2,lease_owner="dead",leased_at=_expired_lease())
    query("UPDATE runs SET status='running' WHERE id=?",(run_id,))
    requeued=recover_stuck_runs(app_env["redis"])
    assert requeued==[]
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="failed" and "重试" in row["error"]


# ---------- 场景 4：已完成/归档成果保持原样，陈旧计算不能覆盖新结果 ----------
def test_completed_run_never_reexecuted(app_env,study_id):
    run_id=_insert_run(study_id,"queued")
    assert execute_run(run_id,worker_id="worker-1") is True
    before=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    # 伪造一个过期租约的“僵尸 running”状态也不应影响 completed 行
    query("UPDATE runs SET leased_at=? WHERE id=?",(_expired_lease(),run_id))
    assert recover_stuck_runs(app_env["redis"])==[]
    assert claim_run(run_id,"zombie") is None
    after=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert after["status"]=="completed" and after["result"]==before["result"]
    assert after["attempt"]==before["attempt"]


def test_archived_report_profiles_stay_locked(app_env,study_id):
    from src.schemas.report import ReportIn
    from src.services.reports import create_report,archive_report
    run_id=_insert_run(study_id,"queued")
    execute_run(run_id,worker_id="worker-1")
    report=create_report(ReportIn(run_id=run_id,title="归档成果"))
    archive_report(report["id"],{"name":"林站长"})
    # 归档后任何重复投递都不能改动运行与类型
    app_env["redis"].rpush(runs.QUEUE,run_id)
    assert execute_run(app_env["redis"].lpop(runs.QUEUE).decode(),worker_id="worker-2") is False
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="completed" and row["attempt"]==1
    profiles_before=query("SELECT * FROM profiles WHERE run_id=? ORDER BY cluster_id",(run_id,))
    # 再次恢复扫描也不会碰它
    assert recover_stuck_runs(app_env["redis"])==[]
    profiles_after=query("SELECT * FROM profiles WHERE run_id=? ORDER BY cluster_id",(run_id,))
    assert profiles_after==profiles_before


def test_stale_attempt_cannot_overwrite_newer_result(app_env,study_id):
    """旧 worker 复活后拿着过期 attempt 提交，必须被击剑校验拒绝。"""
    run_id=_insert_run(study_id,"queued")
    # worker-A 认领到 attempt=1 后“卡死”
    claim=claim_run(run_id,"worker-A")
    assert claim["attempt"]==1
    query("UPDATE runs SET leased_at=? WHERE id=?",(_expired_lease(),run_id))
    # worker-B 接管并完成（attempt=2）
    claim2=claim_run(run_id,"worker-B")
    assert claim2["attempt"]==2
    # 用真实算法产出一份结果，由 B 正常提交
    from src.services.studies import get_study
    from src.services.datasets import get_dataset
    from src.services.algorithms import analyze
    study=get_study(study_id); dataset=get_dataset(study["dataset_id"])
    result=analyze(dataset["rows"],study["features"],study["min_k"],study["max_k"],
                   study["bootstrap"],study["seed"])
    assert finalize_run(run_id,"worker-B",2,result) is True
    completed=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert completed["status"]=="completed"
    # 僵尸 worker-A 醒来，用旧 attempt 提交旧计算 → 必须拒绝
    stale=dict(result); stale["selected_k"]=99
    assert finalize_run(run_id,"worker-A",1,stale) is False
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["result"]["selected_k"]==result["selected_k"]
    assert row["status"]=="completed" and row["attempt"]==2
    # 旧 attempt 写失败状态同样不能覆盖
    assert fail_run(run_id,"worker-A",1,"僵尸报错") is False
    assert decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))["status"]=="completed"
    # artifact 文件也未被陈旧结果覆盖
    on_disk=json.loads((app_env["artifact"]/"runs"/f"{run_id}.json").read_text())
    assert on_disk["selected_k"]==result["selected_k"]


def test_failed_run_retry_succeeds_and_keeps_single_profile_set(app_env,study_id,monkeypatch):
    """失败后重试：首次执行报错落 failed，恢复重投后成功，profiles 不重复。"""
    run_id=_insert_run(study_id,"queued")
    _orig_analyze=runs.analyze
    def boom(*a,**k): raise RuntimeError("模拟计算进程异常退出")
    monkeypatch.setattr(runs,"analyze",boom)
    assert execute_run(run_id,worker_id="worker-flaky") is False
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="failed" and "模拟计算进程异常退出" in row["error"]
    assert _profile_count(run_id)==0
    monkeypatch.setattr(runs,"analyze",_orig_analyze)
    # 失败任务重新投递（恢复扫描会把 failed 留给显式重投；这里直接入队验证 claim 接受 failed）
    app_env["redis"].rpush(runs.QUEUE,run_id)
    assert execute_run(app_env["redis"].lpop(runs.QUEUE).decode(),worker_id="worker-ok") is True
    row=decode(query("SELECT * FROM runs WHERE id=?",(run_id,),one=True))
    assert row["status"]=="completed" and row["attempt"]==2
    assert _profile_count(run_id)==len(row["result"]["profiles"])


def test_heartbeat_renews_lease_and_detects_loss(app_env,study_id,monkeypatch):
    monkeypatch.setattr(settings,"RUN_LEASE_SECONDS",2)
    run_id=_insert_run(study_id,"queued")
    claim=claim_run(run_id,"worker-hb")
    # 模拟 execute_run 内部心跳线程
    import threading as th
    stop=th.Event(); lost=th.Event()
    t=th.Thread(target=runs._heartbeat,args=(run_id,"worker-hb",claim["attempt"],stop,lost),daemon=True)
    t.start()
    time.sleep(1.2)
    leased=query("SELECT leased_at FROM runs WHERE id=?",(run_id,),one=True)["leased_at"]
    assert leased>_expired_lease()  # 租约被持续刷新
    # 租约被别的 owner 抢走后，心跳应感知丢失
    query("UPDATE runs SET lease_owner='worker-new',attempt=attempt+1 WHERE id=?",(run_id,))
    time.sleep(1.2)
    assert lost.is_set()
    stop.set()
