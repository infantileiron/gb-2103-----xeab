import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
class ErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        try: return await call_next(request)
        except ValueError as exc: return JSONResponse({"detail":str(exc)},status_code=422)
        except Exception:
            logging.exception("request_failed")
            return JSONResponse({"detail":"服务暂不可用，请重试或联系站长"},status_code=500)
