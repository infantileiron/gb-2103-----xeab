from fastapi import APIRouter,Depends,Response
from src.utils.security import current_user
from src.schemas.auth import LoginIn
from src.schemas.dataset import DatasetIn
from src.schemas.study import StudyIn
from src.schemas.run import RunIn
from src.schemas.profile import ProfileIn
from src.schemas.report import ReportIn
from src.controllers import auth,datasets,studies,runs,profiles,reports
from src.utils.database import query
router=APIRouter()
@router.post("/auth/login")
def login(data:LoginIn): return auth.login(data)
@router.get("/auth/me")
def me(user=Depends(current_user)): return user
@router.get("/datasets")
def dataset_list(user=Depends(current_user)): return datasets.list_all()
@router.get("/datasets/{id}")
def dataset_detail(id:str,user=Depends(current_user)): return datasets.detail(id)
@router.post("/datasets",status_code=201)
def dataset_create(data:DatasetIn,user=Depends(current_user)): return datasets.create(data,user)
@router.get("/studies")
def study_list(user=Depends(current_user)): return studies.list_all()
@router.post("/studies",status_code=201)
def study_create(data:StudyIn,user=Depends(current_user)): return studies.create(data,user)
@router.get("/runs")
def run_list(user=Depends(current_user)): return runs.list_all()
@router.get("/runs/{id}")
def run_detail(id:str,user=Depends(current_user)): return runs.detail(id)
@router.post("/runs",status_code=201)
def run_create(data:RunIn,user=Depends(current_user)): return runs.create(data,user)
@router.get("/profiles")
def profile_list(run_id:str|None=None,user=Depends(current_user)): return profiles.list_all(run_id)
@router.patch("/profiles/{id}")
def profile_update(id:str,data:ProfileIn,user=Depends(current_user)): return profiles.update(id,data,user)
@router.get("/reports")
def report_list(user=Depends(current_user)): return reports.list_all()
@router.post("/reports",status_code=201)
def report_create(data:ReportIn,user=Depends(current_user)): return reports.create(data,user)
@router.post("/reports/{id}/archive")
def report_archive(id:str,user=Depends(current_user)): return reports.archive(id,user)
@router.get("/reports/{id}/export")
def report_export(id:str,user=Depends(current_user)): return Response(reports.export(id,user),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="estuary-{id}.csv"'})
@router.get("/audits")
def audits(user=Depends(current_user)):
    from src.utils.security import require_admin
    require_admin(user)
    return query("SELECT * FROM audits ORDER BY created_at DESC LIMIT 100")
