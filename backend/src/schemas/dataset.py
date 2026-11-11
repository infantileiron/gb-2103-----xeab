from pydantic import BaseModel, Field
class DatasetIn(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    filename:str=Field(min_length=4,max_length=120)
    rows:list[dict]=Field(min_length=10,max_length=5000)
