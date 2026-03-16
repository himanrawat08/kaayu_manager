from datetime import datetime, timezone, timedelta

_IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Return current naive datetime in IST (UTC+5:30)."""
    return datetime.now(_IST).replace(tzinfo=None)
