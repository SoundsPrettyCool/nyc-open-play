"""Parse NYC Parks athletic-field slot responses (no network; build.py fetches).

Endpoint (undocumented; backs the NYC Parks Field & Court Permit Availability Map):
    $NYC_PARKS_SLOTS_API_URL?systemId=<SYSTEM>&startDate=YYYY-MM-DD

`systemId` is the Athletic Facilities (qnem-b8re) `system` field. One response covers
7 days. `availability` maps a Unix timestamp (start of a 30-minute slot) to details;
slots that aren't listed are available. Validated against the map in
docs/VALIDATION_FINDINGS.md §7 (100% on 252 Chelsea Park slots).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
SLOT = timedelta(minutes=30)


def slot_state(v: dict) -> str:
    """'booked'  : issued permit (the map shows Unavailable)
    'awaiting' : permit awaiting final approval, holder attached (map: Unavailable)
    'pending'  : application only, no holder yet (map: "*Available")"""
    if v.get("is_issued"):
        return "booked"
    if v.get("permit_holder"):
        return "awaiting"
    return "pending"


def blocks_play(state: str) -> bool:
    return state in ("booked", "awaiting")


def to_intervals(availability: dict) -> list[dict]:
    """Merge consecutive 30-minute slots with the same permit/state into intervals,
    in New York local time."""
    rows = sorted(
        (datetime.fromtimestamp(int(ts), NY).replace(tzinfo=None), v) for ts, v in availability.items()
    )
    out: list[dict] = []
    for start, v in rows:
        rec = {
            "state": slot_state(v),
            "permit": v.get("permit_number"),
            "holder": v.get("permit_holder"),
            "type": (v.get("permit_type") or "").replace("Sport - ", "") or None,
            "overlapping": bool(v.get("permit_is_for_overlapping_field")),
        }
        prev = out[-1] if out else None
        if prev and prev["_end"] == start and all(prev[k] == rec[k] for k in rec):
            prev["_end"] = start + SLOT
        else:
            out.append({**rec, "_start": start, "_end": start + SLOT})
    return [
        {"start": r.pop("_start").strftime("%Y-%m-%dT%H:%M"), "end": r.pop("_end").strftime("%Y-%m-%dT%H:%M"), **r}
        for r in out
    ]


def close_times(response: dict) -> dict[str, str]:
    """{'2026-11-01': '22:00', ...} from the response's 'close' map ('10:00 PM')."""
    out = {}
    for day, t in (response.get("close") or {}).items():
        try:
            out[day] = datetime.strptime(t.strip(), "%I:%M %p").strftime("%H:%M")
        except ValueError:
            continue
    return out
