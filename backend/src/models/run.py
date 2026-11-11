from dataclasses import dataclass
from src.constants.enums import RunStatus
@dataclass
class ClusterRun:
    id:str
    study_id:str
    status:RunStatus
    result:dict|None=None
