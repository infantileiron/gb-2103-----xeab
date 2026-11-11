import logging,threading,time
from pathlib import Path
from src.config.settings import WORKER_ID
from src.utils.queue import QUEUE,get_redis
from src.utils.database import initialize
from src.services.runs import execute_run,recovery_loop,recover_stuck_runs

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger=logging.getLogger("estuary.worker")

def main():
    initialize()
    logger.info("worker_started",extra={"worker_id":WORKER_ID})
    redis=get_redis()
    stop_event=threading.Event()
    # 启动即回收上次进程退出遗留的 queued/running 任务
    try:
        recover_stuck_runs(redis)
    except Exception:
        logger.exception("startup_recovery_failed")
    sweeper=threading.Thread(
        target=recovery_loop,args=(redis,stop_event),name="recovery",daemon=True,
    )
    sweeper.start()
    try:
        while True:
            Path("/tmp/worker-heartbeat").write_text(str(time.time()))
            try:
                item=redis.blpop(QUEUE,timeout=5)
                if item:
                    # execute_run 内部完成原子认领；重复/陈旧消息会被安全跳过
                    execute_run(item[1].decode(),worker_id=WORKER_ID)
            except Exception:
                logger.exception("worker_iteration_failed")
                time.sleep(2)
    finally:
        stop_event.set()

if __name__=="__main__": main()
