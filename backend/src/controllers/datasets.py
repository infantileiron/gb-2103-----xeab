from src.services import datasets
from src.utils.security import require_write

def list_all(): return datasets.list_datasets()
def detail(id): return datasets.get_dataset(id)
def create(data,user):
    require_write(user)
    return datasets.create_dataset(data)
