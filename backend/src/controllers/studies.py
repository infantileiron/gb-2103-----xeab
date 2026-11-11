from src.services import studies
from src.utils.security import require_write

def list_all(): return studies.list_studies()
def create(data,user):
    require_write(user)
    return studies.create_study(data)
