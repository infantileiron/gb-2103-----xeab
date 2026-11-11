import logging,time
from pathlib import Path
from redis import Redis
from src.config.settings import REDIS_URL
from src.utils.queue import QUEUE
from src.utils.database import initialize
from src.services.runs import execute_run

def main():
    initialize()
    redis=Redis.from_url(REDIS_URL,socket_connect_timeout=3)
    while True:
        Path("/tmp/worker-heartbeat").write_text(str(time.time()))
        try:
            item=redis.blpop(QUEUE,timeout=5)
            if item: execute_run(item[1].decode())
        except Exception:
            logging.exception("worker_iteration_failed")
            time.sleep(2)
if __name__=="__main__": main()
