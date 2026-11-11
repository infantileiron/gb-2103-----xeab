"""Natural keys preserve existing user edits on repeated seeds."""
import json
import numpy as np
from src.utils.database import initialize,query
from src.utils.security import hash_password
from src.utils.identifiers import new_id,now
from src.schemas.study import StudyIn
from src.schemas.report import ReportIn
from src.services.studies import create_study
from src.services.runs import execute_run
from src.services.reports import create_report

def demo_rows():
    rng=np.random.default_rng(2611)
    centers=np.array([[3.2,8.3,9.2,5.1],[14.8,5.1,27.0,17.3],[29.4,3.0,58.0,35.1]])
    scales=np.array([1.0,.45,3.8,2.0]); rows=[]
    for i in range(360):
        c=i%3; x=np.maximum(centers[c]+rng.normal(size=4)*scales,.1)
        rows.append({"sample_id":f"BLW-{i+1:04d}","section":f"断面 {i%6+1}","sampled_at":"2026-11-10","salinity":round(float(x[0]),3),"oxygen":round(float(x[1]),3),"turbidity":round(float(x[2]),3),"chlorophyll":round(float(x[3]),3)})
    return rows

def seed():
    initialize()
    for role,name in [("admin","林站长"),("analyst","陈研究员"),("viewer","生态观察员")]:
        if not query("SELECT id FROM users WHERE email=?",(role+"@estuary.local",),one=True):
            query("INSERT INTO users VALUES (?,?,?,?,?)",(new_id(),role+"@estuary.local",name,role,hash_password("Estuary2611!")))
    dataset=query("SELECT id FROM datasets WHERE name=?",("十一月河口样方联合调查",),one=True)
    if not dataset:
        id=new_id(); query("INSERT INTO datasets VALUES (?,?,?,?,?)",(id,"十一月河口样方联合调查","ecoplots_202611.csv",json.dumps(demo_rows(),ensure_ascii=False),now()));dataset={"id":id}
    for name,seed_value in [("主航道生态分型 · 11月",2611),("支汊稳定性复核",2026)]:
        study=query("SELECT id FROM studies WHERE name=?",(name,),one=True)
        if not study: study=create_study(StudyIn(name=name,dataset_id=dataset["id"],bootstrap=12,seed=seed_value))
        existing=query("SELECT id FROM runs WHERE study_id=?",(study["id"],),one=True)
        if not existing:
            run_id=new_id();query("INSERT INTO runs VALUES (?,?,?,?,?,?)",(run_id,study["id"],"queued",None,None,now()));execute_run(run_id)
            report=create_report(ReportIn(run_id=run_id,title=name+" · 成果记录"))
            if seed_value==2611: query("UPDATE reports SET status='archived',archived_by='林站长' WHERE id=?",(report["id"],))
    counts={table:query(f"SELECT COUNT(*) AS count FROM {table}",one=True)["count"] for table in ["users","datasets","studies","runs","profiles","reports"]}
    print(json.dumps(counts,ensure_ascii=False))
    return counts
if __name__=="__main__": seed()
