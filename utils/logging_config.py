import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from schemas.utils import ConfigureLoggingInput, SetRequestIdInput

REQUEST_ID = contextvars.ContextVar("request_id", default=None)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = REQUEST_ID.get()
        if rid:
            base["request_id"] = rid
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str)

def configure_logging(data: ConfigureLoggingInput):
    level = data.level
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(level)
    return logging.getLogger("unified-mcp")

def set_request_id(data: SetRequestIdInput):
    try:
        REQUEST_ID.set(data.rid)
    except Exception:
        pass
