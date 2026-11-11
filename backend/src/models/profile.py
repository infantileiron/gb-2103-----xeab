from dataclasses import dataclass
@dataclass
class HabitatProfile:
    id:str
    run_id:str
    cluster_id:int
    name:str
    notes:str
    centroid:dict
    size:int
