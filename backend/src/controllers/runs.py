from src.services import runs
from src.utils.security import require_write

def list_all(): return runs.list_runs()
def detail(id): return runs.get_run(id)
def create(data,user):
    require_write(user)
    return runs.create_run(data.study_id)
