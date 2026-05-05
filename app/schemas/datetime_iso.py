"""RFC 3339 UTC with Z suffix for JSON — avoids clients treating naive ISO as local wall time."""

from datetime import UTC, datetime


def datetime_to_rfc3339_utc_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")
