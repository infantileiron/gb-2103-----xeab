from dataclasses import dataclass
@dataclass
class ClusterStudy:
    id:str
    name:str
    dataset_id:str
    features:list
    min_k:int
    max_k:int
    bootstrap:int
    seed:int
