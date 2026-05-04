"""
AST Capital — Market Hours & Session Detection
Forex is open Sunday 22:00 UTC → Friday 22:00 UTC (24/5).
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta


# Sessions defined by UTC hour range (start_inclusive, end_exclusive)
_SESSIONS = [
    (22, 24, "Sydney"),     # 22-00 UTC
    (0,   2, "Sydney"),     # 00-02 UTC (same session, next day)
    (0,   9, "Tokyo"),      # 00-09 UTC
    (8,  17, "London"),     # 08-17 UTC
    (13, 17, "London / New York"),  # 13-17 peak overlap
    (13, 22, "New York"),   # 13-22 UTC
]


def _current_session(hour: int) -> str:
    """Return the primary session name for a given UTC hour."""
    # Overlap takes priority
    if 13 <= hour < 17:
        return "London / New York  ← peak liquidity"
    if 8 <= hour < 13:
        return "London"
    if 13 <= hour < 22:
        return "New York"
    if 0 <= hour < 2:
        return "Sydney / Tokyo"
    if 2 <= hour < 9:
        return "Tokyo"
    return "Sydney"


def get_market_status(symbol: str = "EURUSD") -> dict:
    """
    Return a dict describing whether the forex market is open.
    Source of truth is the weekday + UTC hour.
    """
    now = datetime.now(timezone.utc)
    wd  = now.weekday()   # 0=Mon … 6=Sun
    h   = now.hour
    m   = now.minute

    closed_reason = None
    if wd == 5:                       # Saturday — always closed
        closed_reason = "Weekend (Saturday)"
    elif wd == 6 and (h < 22):        # Sunday before 22:00 UTC
        opens_in = timedelta(hours=(22 - h - 1), minutes=(60 - m))
        closed_reason = f"Weekend — opens in {_fmt_delta(opens_in)}"
    elif wd == 4 and h >= 22:         # Friday after 22:00 UTC
        closed_reason = "Weekend — opens Sunday 22:00 UTC"

    if closed_reason:
        return {
            "open":        False,
            "session":     "Closed",
            "reason":      closed_reason,
            "utc_time":    now.strftime("%Y-%m-%d %H:%M UTC"),
            "next_open":   _next_open(now),
        }

    session = _current_session(h)
    return {
        "open":        True,
        "session":     session,
        "reason":      "Market open",
        "utc_time":    now.strftime("%Y-%m-%d %H:%M UTC"),
        "next_open":   None,
    }


def _fmt_delta(td: timedelta) -> str:
    total = int(td.total_seconds())
    h, rem = divmod(total, 3600)
    m = rem // 60
    return f"{h}h {m}m" if h else f"{m}m"


def _next_open(now: datetime) -> str:
    """Return a human-readable string for the next market open."""
    wd = now.weekday()
    if wd == 4 and now.hour >= 22:   # Friday evening
        days_until = 2
    elif wd == 5:                     # Saturday
        days_until = 1
    else:                             # Sunday before 22
        days_until = 0

    target = now + timedelta(days=days_until)
    target = target.replace(hour=22, minute=0, second=0, microsecond=0)
    if wd == 6 and now.hour < 22:
        target = now.replace(hour=22, minute=0, second=0, microsecond=0)

    return target.strftime("%A %d %b — 22:00 UTC")
