import os,sys,json,pathlib,tempfile
import fakeredis
import pytest

# 必须在任何 src.* 模块导入之前配置环境变量（settings 在导入时读取它们）
_ROOT=tempfile.TemporaryDirectory()
os.environ.setdefault("DATABASE_URL","sqlite:///"+str(pathlib.Path(_ROOT.name)/"bootstrap.sqlite3"))
os.environ["ARTIFACT_DIR"]=str(pathlib.Path(_ROOT.name)/"artifacts")
os.environ["TASK_MODE"]="redis"
os.environ.setdefault("RUN_LEASE_SECONDS","300")
os.environ.setdefault("RUN_MAX_ATTEMPTS","5")
os.environ.setdefault("RECOVERY_INTERVAL_SECONDS","60")

BACKEND=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))

_TABLES=("audits","reports","profiles","runs","studies","datasets","users")

@pytest.fixture()
def app_env(monkeypatch):
    # 每个用例独立数据库文件，彻底隔离（含改表结构的迁移测试）
    tmp=tempfile.TemporaryDirectory()
    db_path=pathlib.Path(tmp.name)/"test.sqlite3"
    artifact=pathlib.Path(tmp.name)/"artifacts"
    from src.utils import database,queue
    from src.config import settings
    from src.services import runs as runs_svc
    monkeypatch.setattr(database,"DATABASE_URL",f"sqlite:///{db_path}")
    monkeypatch.setattr(settings,"ARTIFACT_DIR",str(artifact))
    monkeypatch.setattr(runs_svc,"ARTIFACT_DIR",str(artifact))
    database.initialize()
    fake=fakeredis.FakeStrictRedis(decode_responses=False)
    monkeypatch.setattr(queue,"get_redis",lambda: fake)
    yield {"tmp":tmp,"artifact":artifact,"redis":fake,"db_path":db_path}
    tmp.cleanup()

@pytest.fixture()
def study_id(app_env):
    import numpy as np
    from src.utils.database import query
    from src.utils.identifiers import new_id,now
    from src.schemas.study import StudyIn
    from src.services.studies import create_study
    rng=np.random.default_rng(7)
    centers=np.array([[3.0,8.0,9.0,5.0],[15.0,5.0,27.0,17.0],[29.0,3.0,58.0,35.0]])
    rows=[]
    for i in range(120):
        c=i%3
        x=np.maximum(centers[c]+rng.normal(size=4)*0.8,0.1)
        rows.append({"sample_id":f"S-{i:04d}","section":f"断面{i%4+1}",
                     "salinity":round(float(x[0]),3),"oxygen":round(float(x[1]),3),
                     "turbidity":round(float(x[2]),3),"chlorophyll":round(float(x[3]),3)})
    ds_id=new_id()
    query("INSERT INTO datasets VALUES (?,?,?,?,?)",
          (ds_id,"测试数据集","demo.csv",json.dumps(rows,ensure_ascii=False),now()))
    study=create_study(StudyIn(name="崩溃恢复测试研究",dataset_id=ds_id,
                               features=["salinity","oxygen","turbidity","chlorophyll"],
                               min_k=2,max_k=4,bootstrap=6,seed=2611))
    return study["id"]
