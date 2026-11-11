import base64,hashlib,hmac,json,secrets,time
from src.config.settings import JWT_SECRET
from fastapi import HTTPException,Header
from src.utils.database import query

def hash_password(password):
    salt=secrets.token_hex(16)
    return salt+":"+hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),180000).hex()
def check_password(password,stored):
    salt,digest=stored.split(":")
    actual=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),180000).hex()
    return hmac.compare_digest(actual,digest)
def b64(data): return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
def token_for(user):
    head=b64(json.dumps({"alg":"HS256","typ":"JWT"}).encode())
    payload=b64(json.dumps({"sub":user["id"],"exp":int(time.time())+8*3600}).encode())
    body=head+"."+payload
    return body+"."+b64(hmac.new(JWT_SECRET.encode(),body.encode(),hashlib.sha256).digest())
def current_user(authorization: str=Header(default="")):
    try:
        token=authorization.split(" ",1)[1]
        head,payload,sig=token.split(".")
        expected=b64(hmac.new(JWT_SECRET.encode(),(head+"."+payload).encode(),hashlib.sha256).digest())
        assert hmac.compare_digest(sig,expected)
        data=json.loads(base64.urlsafe_b64decode(payload+"="*(-len(payload)%4)))
        assert data["exp"]>time.time()
        user=query("SELECT id,email,name,role FROM users WHERE id=?",(data["sub"],),one=True)
        assert user
        return user
    except Exception: raise HTTPException(401,"登录已失效，请重新登录")
def require_write(user):
    if user["role"] not in ("admin","analyst"): raise HTTPException(403,"观察员只可读取成果")
def require_admin(user):
    if user["role"]!="admin": raise HTTPException(403,"仅站长可审核归档")
