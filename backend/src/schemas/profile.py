from pydantic import BaseModel,Field
class ProfileIn(BaseModel):
    name:str=Field(min_length=2,max_length=60)
    notes:str=Field(default="",max_length=1000)
