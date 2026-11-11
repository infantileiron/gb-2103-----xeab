from pydantic import BaseModel, Field, model_validator
from src.constants.enums import FEATURES
class StudyIn(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    dataset_id:str
    features:list[str]=Field(default=list(FEATURES),min_length=2,max_length=4)
    min_k:int=Field(default=2,ge=2,le=6)
    max_k:int=Field(default=5,ge=2,le=6)
    bootstrap:int=Field(default=20,ge=5,le=60)
    seed:int=Field(default=2611,ge=0,le=2147483647)
    @model_validator(mode="after")
    def valid(self):
        if self.min_k>self.max_k: raise ValueError("最小分组数不可超过最大值")
        if len(set(self.features))!=len(self.features) or set(self.features)-set(FEATURES): raise ValueError("特征列表包含重复或未知字段")
        return self
