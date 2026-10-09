"""Trace-id context + structured-ish logging [TECH]."""
import contextvars
import logging
import uuid

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] trace=%(message)s",
)


def new_trace_id() -> str:
    tid = "trc_" + uuid.uuid4().hex[:16]
    _trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    return _trace_id.get()


def set_trace_id(tid: str):
    _trace_id.set(tid)


def log(name: str) -> logging.LoggerAdapter:
    base = logging.getLogger(name)

    class _A(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            return f"{get_trace_id()} {msg}", kwargs

    return _A(base, {})
