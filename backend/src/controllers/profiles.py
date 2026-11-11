from src.services import profiles
from src.utils.security import require_write

def list_all(run_id): return profiles.list_profiles(run_id)
def update(id,data,user):
    require_write(user)
    return profiles.update_profile(id,data)
