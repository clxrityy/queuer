from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


UTC = timezone.utc


def validate_timezone_name(value: str) -> str:
    timezone_name = value.strip()
    if not timezone_name:
        raise ValueError("Timezone cannot be empty.")

    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc
    return timezone_name


def parse_time_string(value: str) -> time:
    normalized = value.strip()
    try:
        parsed = datetime.strptime(normalized, "%H:%M")
    except ValueError as exc:
        raise ValueError("Time must use 24-hour HH:MM format.") from exc
    return parsed.time().replace(second=0, microsecond=0)


def normalize_schedule_time(value: str) -> str:
    return parse_time_string(value).strftime("%H:%M")


def parse_utc_timestamp(value: str) -> datetime:
    normalized = value.strip().replace(" ", "T")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_schedule_override(
    schedule_date: Optional[str],
    schedule_time: Optional[str],
    timezone_name: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    if schedule_date is None and schedule_time is None:
        return None
    if not schedule_date or not schedule_time:
        raise ValueError("Schedule override requires both date and time.")

    timezone_key = validate_timezone_name(timezone_name)
    try:
        parsed_date = date.fromisoformat(schedule_date.strip())
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD format.") from exc

    parsed_time = parse_time_string(schedule_time)
    local_dt = datetime.combine(parsed_date, parsed_time).replace(tzinfo=ZoneInfo(timezone_key))
    scheduled_for = local_dt.astimezone(UTC)

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    else:
        current = current.astimezone(UTC)

    if scheduled_for <= current:
        raise ValueError("Scheduled time must be in the future.")
    return scheduled_for


def is_daily_schedule_due(
    now: datetime,
    schedule_time: str,
    timezone_name: str,
    *,
    last_sent_at: Optional[datetime] = None,
) -> bool:
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    current = current.astimezone(UTC)
    timezone_key = validate_timezone_name(timezone_name)
    local_now = current.astimezone(ZoneInfo(timezone_key))
    scheduled_local = datetime.combine(local_now.date(), parse_time_string(schedule_time)).replace(
        tzinfo=ZoneInfo(timezone_key)
    )
    scheduled_utc = scheduled_local.astimezone(UTC)
    if current < scheduled_utc:
        return False
    if last_sent_at is None:
        return True
    latest = last_sent_at if last_sent_at.tzinfo is not None else last_sent_at.replace(tzinfo=UTC)
    return latest.astimezone(UTC) < scheduled_utc


def format_utc_for_display(value: str, timezone_name: str) -> str:
    timezone_key = validate_timezone_name(timezone_name)
    localized = parse_utc_timestamp(value).astimezone(ZoneInfo(timezone_key))
    return f"{localized.strftime('%Y-%m-%d %H:%M')} {timezone_key}"