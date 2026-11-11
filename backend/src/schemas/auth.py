from pydantic import BaseModel, Field
class LoginIn(BaseModel):
    email:str
    password:str=Field(min_length=1,max_length=200)
