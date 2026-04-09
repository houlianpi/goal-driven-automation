"""Shared timezone-aware UTC helpers."""
from datetime import datetime, timezone


UTC = timezone.utc


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Normalize legacy naive datetimes to UTC for safe comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_datetime(value: str) -> datetime:
    """Parse ISO timestamps and normalize them to UTC."""
    return ensure_utc(datetime.fromisoformat(value))
