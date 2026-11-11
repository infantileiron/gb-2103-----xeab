import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.utils.database import initialize,query
from src.config.settings import SEED_DEMO,TASK_MODE,REDIS_URL
from src.routes.api import router
from src.middlewares.audit import AuditMiddleware
from src.middlewares.errors import ErrorMiddleware
@asynccontextmanager
async def lifespan(app):
    initialize()
    if SEED_DEMO:
        try:
            from scripts.seed_demo import seed
            seed()
        except Exception: logging.exception("demo_seed_failed")
    yield
app=FastAPI(title="白鹭湾河口样方生态分型",lifespan=lifespan)
app.add_middleware(AuditMiddleware)
app.add_middleware(ErrorMiddleware)
app.include_router(router)
@app.get("/health")
def health():
    query("SELECT 1")
    if TASK_MODE!="inline":
        from redis import Redis
        Redis.from_url(REDIS_URL,socket_connect_timeout=2).ping()
    return {"status":"ok","task_mode":TASK_MODE}
