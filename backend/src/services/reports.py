import csv,io,json
from fastapi import HTTPException
from src.utils.database import query,decode
from src.utils.identifiers import new_id,now
from src.services.runs import get_run
from src.models.report import Report
from src.constants.enums import ReportStatus

def list_reports(): return query("SELECT * FROM reports ORDER BY created_at DESC")
def create_report(data):
    run=get_run(data.run_id)
    if run["status"]!="completed": raise HTTPException(409,"请先完成分型计算")
    item=Report(new_id(),data.run_id,data.title,ReportStatus.draft)
    query("INSERT INTO reports VALUES (?,?,?,?,?,?)",(item.id,item.run_id,item.title,item.status.value,now(),None))
    return query("SELECT * FROM reports WHERE id=?",(item.id,),one=True)
def archive_report(id,user):
    report=query("SELECT * FROM reports WHERE id=?",(id,),one=True)
    if not report: raise HTTPException(404,"成果不存在")
    query("UPDATE reports SET status='archived',archived_by=? WHERE id=?",(user["name"],id))
    return query("SELECT * FROM reports WHERE id=?",(id,),one=True)
def export_report(id,user):
    report=query("SELECT * FROM reports WHERE id=?",(id,),one=True)
    if not report: raise HTTPException(404,"成果不存在")
    if user["role"]=="viewer" and report["status"]!="archived": raise HTTPException(403,"观察员只可下载已归档成果")
    run=get_run(report["run_id"]); result=run["result"]
    profiles={p["cluster_id"]:p for p in query("SELECT * FROM profiles WHERE run_id=?",(run["id"],))}
    output=io.StringIO(); output.write("\ufeff"); writer=csv.writer(output)
    writer.writerow(["样方编号","采样断面","生态类型",*result["features"],"轮廓系数","平均ARI","随机种子","输入SHA256"])
    for p in result["points"]:
        writer.writerow([p["sample_id"],p["section"],profiles[p["cluster"]]["name"],*[p["values"][f] for f in result["features"]],result["silhouette"],result["stability"]["mean_ari"],result["seed"],result["checksum"]])
    return output.getvalue()
