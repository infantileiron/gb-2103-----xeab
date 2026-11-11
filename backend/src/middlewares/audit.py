from starlette.middleware.base import BaseHTTPMiddleware
from src.utils.database import query
from src.utils.identifiers import new_id,now
class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        response=await call_next(request)
        if request.method in ("POST","PATCH","DELETE"):
            actor="anonymous"
            try:
                from src.utils.security import current_user
                actor=current_user(request.headers.get("authorization",""))["email"]
            except Exception: pass
            query("INSERT INTO audits VALUES (?,?,?,?,?,?)",(new_id(),actor,request.method,request.url.path,response.status_code,now()))
        return response
