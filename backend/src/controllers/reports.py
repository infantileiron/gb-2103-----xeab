from src.services import reports
from src.utils.security import require_write,require_admin

def list_all(): return reports.list_reports()
def create(data,user):
    require_write(user)
    return reports.create_report(data)
def archive(id,user):
    require_admin(user)
    return reports.archive_report(id,user)
def export(id,user): return reports.export_report(id,user)
