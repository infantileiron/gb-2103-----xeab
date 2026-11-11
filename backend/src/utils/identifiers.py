from uuid import uuid4
from datetime import datetime, timezone
def new_id(): return str(uuid4())
def now(): return datetime.now(timezone.utc).isoformat()
