from fastapi import HTTPException
from src.utils.database import query
from src.utils.security import check_password,token_for

def login(data):
    user=query("SELECT * FROM users WHERE email=?",(data.email,),one=True)
    if not user or not check_password(data.password,user["password_hash"]): raise HTTPException(401,"账号或密码不正确")
    return {"token":token_for(user),"user":{k:user[k] for k in ("id","email","name","role")}}
