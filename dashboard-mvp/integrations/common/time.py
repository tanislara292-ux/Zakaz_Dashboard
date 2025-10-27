"""Utilities for dealing with Moscow time and simple date ranges."""

from __future__ import annotations

import calendar
import logging
import os
from datetime import date, datetime, time as dt_time, timedelta
from typing import Iterable, Optional, Tuple, Union

import pytz

__all__ = [
    "utcnow",
    "now_msk",
    "today_msk",
    "to_msk",
    "to_date",
    "date_range",
    "days_ago",
    "format_msk",
    "is_weekend",
    "parse_period",
]

logger = logging.getLogger(__name__)

DEFAULT_TZ_ENV = "DEFAULT_TZ"
DEFAULT_TZ_FALLBACK = "Europe/Moscow"

_tz_cache_name: Optional[str] = None
_tz_cache = pytz.timezone(DEFAULT_TZ_FALLBACK)


def _load_timezone(name: str) -> pytz.BaseTzInfo:
    """Return a pytz timezone, falling back to the default on errors."""
    try:
        return pytz.timezone(name)
    except pytz.UnknownTimeZoneError:
        logger.warning(
            "Unknown timezone %s, falling back to %s", name, DEFAULT_TZ_FALLBACK
        )
        return pytz.timezone(DEFAULT_TZ_FALLBACK)


def _current_timezone() -> pytz.BaseTzInfo:
    """Return the timezone configured through ``DEFAULT_TZ`` (cached)."""
    global _tz_cache_name, _tz_cache  # pylint: disable=global-statement

    name = os.getenv(DEFAULT_TZ_ENV, DEFAULT_TZ_FALLBACK)
    if name != _tz_cache_name:
        _tz_cache = _load_timezone(name)
        _tz_cache_name = name
    return _tz_cache


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(pytz.UTC)


def now_msk() -> datetime:
    """Return the current time in the configured Moscow timezone."""
    return utcnow().astimezone(_current_timezone())


def today_msk() -> date:
    """Return today's date in the configured Moscow timezone."""
    return now_msk().date()


def _parse_datetime(value: Union[str, datetime, date], fmt: Optional[str]) -> datetime:
    """Coerce common input shapes into a timezone-aware datetime."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, dt_time.min)
    elif isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError("Empty datetime string")
        if fmt:
            dt = datetime.strptime(value, fmt)
        else:
            for pattern in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d",
                "%d.%m.%Y %H:%M:%S",
                "%d.%m.%Y",
            ):
                try:
                    dt = datetime.strptime(value, pattern)
                    break
                except ValueError:
                    continue
            else:
                try:
                    # Last resort: let fromisoformat handle offsets like '+03:00'
                    normalized = value.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(normalized)
                except ValueError as exc:
                    raise ValueError(f"Unsupported datetime string: {value}") from exc
    else:
        raise TypeError(f"Unsupported type for datetime conversion: {type(value)!r}")

    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)

    return dt.astimezone(_current_timezone())


def to_msk(value: Union[str, datetime, date], fmt: Optional[str] = None) -> datetime:
    """Convert the provided value to a timezone-aware datetime in MSK."""
    return _parse_datetime(value, fmt)


def to_date(value: Union[str, datetime, date], fmt: Optional[str] = None) -> date:
    """Convert the provided value to a date in MSK."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return to_msk(value, fmt).date()


def date_range(
    start: Union[str, datetime, date],
    end: Union[str, datetime, date],
    *,
    fmt: Optional[str] = None,
) -> Iterable[date]:
    """Return an inclusive range of dates in MSK."""
    start_date = to_date(start, fmt)
    end_date = to_date(end, fmt)
    if start_date > end_date:
        raise ValueError("start date must not be greater than end date")
    days = (end_date - start_date).days
    for offset in range(days + 1):
        yield start_date + timedelta(days=offset)


def days_ago(days: int) -> date:
    """Return the date ``days`` days ago in MSK."""
    if days < 0:
        raise ValueError("days must be non-negative")
    return today_msk() - timedelta(days=days)


def format_msk(value: Union[str, datetime, date], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format the provided value in MSK using the supplied ``strftime`` pattern."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return to_msk(value).strftime(fmt)


def is_weekend(value: Union[str, datetime, date]) -> bool:
    """Return ``True`` if the supplied date/datetime falls on Saturday or Sunday."""
    return to_date(value).weekday() >= 5


def parse_period(period: str) -> Tuple[date, date]:
    """Parse a textual period descriptor into a ``(start, end)`` tuple (inclusive)."""
    if not period:
        raise ValueError("period must be a non-empty string")

    normalized = period.strip().lower()
    today = today_msk()

    if normalized == "today":
        return today, today
    if normalized == "yesterday":
        y = days_ago(1)
        return y, y
    if normalized == "last_7_days":
        return days_ago(6), today
    if normalized == "last_30_days":
        return days_ago(29), today
    if normalized == "this_month":
        start = today.replace(day=1)
        return start, today
    if normalized == "last_month":
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        return start, end

    if _looks_like_month(normalized):
        year, month = map(int, normalized.split("-"))
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        return start, end

    if _looks_like_date(normalized):
        parsed = to_date(normalized)
        return parsed, parsed

    raise ValueError(f"Unsupported period string: {period}")


def _looks_like_month(value: str) -> bool:
    return len(value) == 7 and value[4] == "-" and value[:4].isdigit() and value[5:].isdigit()


def _looks_like_date(value: str) -> bool:
    return len(value) == 10 and value[4] == "-" and value[7] == "-" and value.replace("-", "").isdigit()
