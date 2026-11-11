from src.config.settings import REDIS_URL,TASK_MODE
QUEUE="estuary:cluster:runs"
def get_redis():
    from redis import Redis
    return Redis.from_url(REDIS_URL,socket_connect_timeout=3,socket_keepalive=True)
def enqueue(run_id):
    if TASK_MODE=="inline":
        from src.services.runs import execute_run
        execute_run(run_id)
    else:
        get_redis().rpush(QUEUE,run_id)
