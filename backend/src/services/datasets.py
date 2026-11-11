import json
from fastapi import HTTPException
from src.utils.database import query,decode
from src.utils.identifiers import new_id,now
from src.services.algorithms import validate_rows
from src.models.dataset import SurveyDataset

def list_datasets():
    rows=[decode(r) for r in query("SELECT * FROM datasets ORDER BY created_at DESC")]
    return [{**{k:v for k,v in r.items() if k!="rows"},"row_count":len(r["rows"]),"sections":sorted(set(x.get("section","未标注") for x in r["rows"]))} for r in rows]
def get_dataset(id):
    row=decode(query("SELECT * FROM datasets WHERE id=?",(id,),one=True))
    if row is None: raise HTTPException(404,"采样批次不存在")
    return row
def create_dataset(data):
    validate_rows(data.rows)
    entity=SurveyDataset(new_id(),data.name,data.filename,data.rows)
    if query("SELECT id FROM datasets WHERE name=?",(data.name,),one=True): raise HTTPException(409,"批次名称已存在")
    query("INSERT INTO datasets VALUES (?,?,?,?,?)",(entity.id,entity.name,entity.filename,json.dumps(entity.rows,ensure_ascii=False),now()))
    return get_dataset(entity.id)
