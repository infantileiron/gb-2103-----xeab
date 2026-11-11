import json
from fastapi import HTTPException
from src.utils.database import query,decode
from src.utils.identifiers import new_id,now
from src.services.datasets import get_dataset
from src.services.algorithms import validate_rows
from src.models.study import ClusterStudy

def list_studies(): return [decode(r) for r in query("SELECT * FROM studies ORDER BY created_at DESC")]
def get_study(id):
    row=decode(query("SELECT * FROM studies WHERE id=?",(id,),one=True))
    if row is None: raise HTTPException(404,"分型研究不存在")
    return row
def create_study(data):
    dataset=get_dataset(data.dataset_id)
    validate_rows(dataset["rows"],data.features)
    if query("SELECT id FROM studies WHERE name=?",(data.name,),one=True): raise HTTPException(409,"研究名称已存在")
    entity=ClusterStudy(new_id(),data.name,data.dataset_id,data.features,data.min_k,data.max_k,data.bootstrap,data.seed)
    query("INSERT INTO studies VALUES (?,?,?,?,?,?,?,?,?)",(entity.id,entity.name,entity.dataset_id,json.dumps(entity.features),entity.min_k,entity.max_k,entity.bootstrap,entity.seed,now()))
    return get_study(entity.id)
