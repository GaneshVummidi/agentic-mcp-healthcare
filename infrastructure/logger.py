"""
Infrastructure Layer -> Logging
Writes System Logs, Error Logs, and Audit Logs to /backend/logs/*.log
"""
import logging
import os
from config import settings

os.makedirs(settings.LOG_DIR, exist_ok=True)


def _make_logger(name: str, filename: str, level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

        fh = logging.FileHandler(os.path.join(settings.LOG_DIR, filename), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    return logger


system_logger = _make_logger("mediaegis.system", "system.log")
error_logger = _make_logger("mediaegis.error", "error.log", level=logging.ERROR)
audit_logger = _make_logger("mediaegis.audit", "audit.log")


def log_audit_event(event: str, session_id: str, details: dict | None = None):
    audit_logger.info(f"session={session_id} event={event} details={details or {}}")
