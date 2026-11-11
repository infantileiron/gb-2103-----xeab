import json
from pathlib import Path
from fastapi import HTTPException
from src.utils.database import query,decode
from src.utils.identifiers import new_id,now
from src.services.studies import get_study
from src.services.datasets import get_dataset
from src.services.algorithms import analyze
from src.utils.queue import enqueue
from src.models.run import ClusterRun
from src.constants.enums import RunStatus
from src.config.settings import ARTIFACT_DIR

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
    query("INSERT INTO runs VALUES (?,?,?,?,?,?)",(entity.id,entity.study_id,entity.status.value,None,None,now()))
    try: enqueue(entity.id)
    except Exception as exc:
        query("UPDATE runs SET status='failed',error=? WHERE id=?",("队列暂不可用，请检查Redis后重试",entity.id))
        raise HTTPException(503,"任务未能入队；恢复队列后可重新运行") from exc
    return get_run(entity.id)
def execute_run(run_id):
    run=get_run(run_id)
    if run["status"] in ("completed","running"): return
    query("UPDATE runs SET status='running',error=NULL WHERE id=?",(run_id,))
    try:
        study=get_study(run["study_id"]); dataset=get_dataset(study["dataset_id"])
        result=analyze(dataset["rows"],study["features"],study["min_k"],study["max_k"],study["bootstrap"],study["seed"])
        output=Path(ARTIFACT_DIR)/"runs"
        output.mkdir(parents=True,exist_ok=True)
        temporary=output/(run_id+".tmp")
        temporary.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
        temporary.replace(output/(run_id+".json"))
        for p in result["profiles"]:
            query("INSERT INTO profiles VALUES (?,?,?,?,?,?,?) ON CONFLICT (run_id,cluster_id) DO NOTHING",(new_id(),run_id,p["cluster_id"],p["name"],"",json.dumps(p["centroid"]),p["size"]))
        query("UPDATE runs SET status='completed',result_json=? WHERE id=?",(json.dumps(result,ensure_ascii=False),run_id))
    except Exception as exc:
        query("UPDATE runs SET status='failed',error=? WHERE id=?",(str(exc)[:500],run_id))
