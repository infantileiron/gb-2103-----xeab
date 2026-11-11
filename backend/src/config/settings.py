import os,uuid
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/estuary-lab.sqlite3")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
JWT_SECRET = os.getenv("JWT_SECRET", "estuary_local_demo_secret_change_before_deploy_2026")
SEED_DEMO = os.getenv("SEED_DEMO", "false").lower() == "true"
TASK_MODE = os.getenv("TASK_MODE", "redis")
ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "/artifacts")
# 崩溃恢复：运行被认领后的租约时长；心跳会持续续租，超过此时长仍未续租视为 worker 已退出
RUN_LEASE_SECONDS = int(os.getenv("RUN_LEASE_SECONDS", "120"))
# 单次运行最大重试次数（不含首次执行），超出后标记 failed 等待人工介入
RUN_MAX_ATTEMPTS = int(os.getenv("RUN_MAX_ATTEMPTS", "5"))
# 周期性扫描卡住任务的间隔
RECOVERY_INTERVAL_SECONDS = int(os.getenv("RECOVERY_INTERVAL_SECONDS", "30"))
WORKER_ID = os.getenv("WORKER_ID", f"{os.uname().nodename}-{os.getpid()}-{uuid.uuid4().hex[:8]}")
