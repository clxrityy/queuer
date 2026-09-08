from __future__ import annotations

from datetime import datetime


def isoformat_utc(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat() + "Z"