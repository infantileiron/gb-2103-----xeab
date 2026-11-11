from dataclasses import dataclass
from src.constants.enums import ReportStatus
@dataclass
class Report:
    id:str
    run_id:str
    title:str
    status:ReportStatus
