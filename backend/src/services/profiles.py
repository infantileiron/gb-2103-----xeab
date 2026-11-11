from fastapi import HTTPException
from src.utils.database import query,decode
from src.models.profile import HabitatProfile

def list_profiles(run_id=None):
    rows=query("SELECT * FROM profiles WHERE run_id=? ORDER BY cluster_id",(run_id,)) if run_id else query("SELECT * FROM profiles ORDER BY run_id,cluster_id")
    return [decode(r) for r in rows]
def update_profile(id,data):
    row=decode(query("SELECT * FROM profiles WHERE id=?",(id,),one=True))
    if not row: raise HTTPException(404,"栖息类型不存在")
    if query("SELECT id FROM reports WHERE run_id=? AND status='archived'",(row["run_id"],),one=True): raise HTTPException(409,"该运行已归档，类型解释已锁定，请新建研究")
    entity=HabitatProfile(**{k:row[k] for k in ("id","run_id","cluster_id","name","notes","centroid","size")})
    query("UPDATE profiles SET name=?,notes=? WHERE id=?",(data.name,data.notes,entity.id))
    return decode(query("SELECT * FROM profiles WHERE id=?",(id,),one=True))
