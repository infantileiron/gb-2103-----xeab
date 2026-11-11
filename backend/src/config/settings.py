import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/estuary-lab.sqlite3")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
JWT_SECRET = os.getenv("JWT_SECRET", "estuary_local_demo_secret_change_before_deploy_2026")
SEED_DEMO = os.getenv("SEED_DEMO", "false").lower() == "true"
TASK_MODE = os.getenv("TASK_MODE", "redis")
ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "/artifacts")
