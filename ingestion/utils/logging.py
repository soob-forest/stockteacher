"""Lightweight structured logging helpers without extra deps."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        if record.args and isinstance(record.args, dict):
            payload.update(record.args)
        # merge extra dict if provided via logger.info(event, extra={...})
        for key, value in record.__dict__.items():
            if key in ("msg", "args", "levelname", "name", "created", "msecs", "relativeCreated"):
                continue
            if key.startswith("_"):
                continue
            if key in payload:
                continue
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level_name: str = "INFO", json_enabled: bool = False) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    # Clear existing handlers to avoid duplicates when reconfiguring
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    if json_enabled:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

