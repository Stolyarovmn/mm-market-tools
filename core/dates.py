#!/usr/bin/env python3
import datetime as dt
import re
from urllib.parse import unquote
from zoneinfo import ZoneInfo


MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def parse_moscow_datetime(value):
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=MOSCOW_TZ)
    return parsed.astimezone(MOSCOW_TZ)


def market_window_bounds(window_days):
    now = dt.datetime.now(MOSCOW_TZ)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999000)
    start_day = (now - dt.timedelta(days=window_days - 1)).date()
    start = dt.datetime.combine(start_day, dt.time.min, tzinfo=MOSCOW_TZ)
    return start, end


def to_epoch_ms(value):
    return int(value.timestamp() * 1000)


def infer_window_from_report_source(value):
    raw = unquote(value or "")
    matches = re.findall(r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})", raw)
    if len(matches) >= 2:
        date_from = dt.datetime.strptime(matches[0], "%d.%m.%Y %H:%M:%S").replace(tzinfo=MOSCOW_TZ)
        date_to = dt.datetime.strptime(matches[1], "%d.%m.%Y %H:%M:%S").replace(tzinfo=MOSCOW_TZ)
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "window_days": round((date_to - date_from).total_seconds() / 86400, 2),
        }
    return {}
