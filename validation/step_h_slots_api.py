"""Step H: check the NYC Parks athletic-field slots API against map screenshots.

The NYC Parks Availability Map is backed by an undocumented JSON endpoint:

    $NYC_PARKS_SLOTS_API_URL?systemId=<SYSTEM>&startDate=YYYY-MM-DD

`systemId` is the Athletic Facilities (qnem-b8re) `system` field, e.g. M011-SOCCER-1.
One response covers 7 days from startDate. `availability` maps a Unix timestamp
(30-minute slot start) to slot details. Slots that aren't listed are available.

    python validation/step_h_slots_api.py                 # Chelsea, both screenshot weeks
    python validation/step_h_slots_api.py --offline       # reuse saved responses

Be polite: honest User-Agent, a delay between requests, and only what's needed.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from common import OUT, session, write_json

API = "$NYC_PARKS_SLOTS_API_URL"
NY = ZoneInfo("America/New_York")
GRIDS = ["ground_truth_chelsea_grid_2026-11-01_week.csv", "ground_truth_chelsea_grid.csv"]


def slot_unavailable(v: dict) -> bool:
    """Unavailable on the map iff a permit holder is attached: issued, or awaiting final
    approval. Slots with only pending applications (no holder) show as "*Available"."""
    return bool(v.get("permit_holder")) or bool(v.get("is_issued"))


def fetch(s, system_id: str, start: str) -> dict:
    r = s.get(API, params={"systemId": system_id, "startDate": start}, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system-id", default="M011-SOCCER-1")
    ap.add_argument("--starts", default="2026-11-01,2026-11-08")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()

    out = OUT / "h"
    out.mkdir(parents=True, exist_ok=True)
    s = session()
    slots = {}
    for i, start in enumerate(a.starts.split(",")):
        path = out / f"{a.system_id}_{start}.json"
        if not a.offline:
            if i:
                time.sleep(a.delay)
            write_json(path, fetch(s, a.system_id, start))
        data = json.loads(path.read_text())
        for ts, v in data["availability"].items():
            slots[datetime.fromtimestamp(int(ts), NY).replace(tzinfo=None)] = v

    tally, mismatches = Counter(), []
    for grid in GRIDS:
        rows = list(csv.reader(line for line in (OUT.parent / grid).open() if not line.startswith("#")))
        header, data = rows[0], rows[1:]
        for j, day in enumerate(header[1:], 1):
            for r in data:
                t = datetime.fromisoformat(f"{day}T{r[0]}")
                site_u = r[j] == "U"
                api_u = t in slots and slot_unavailable(slots[t])
                tally["agree" if site_u == api_u else "disagree"] += 1
                if site_u != api_u:
                    mismatches.append({"slot": str(t), "site": r[j], "api": slots.get(t)})

    n = sum(tally.values())
    kinds = Counter(
        "issued" if v["is_issued"] else "awaiting approval (holder set)" if v["permit_holder"]
        else "pending application only" for v in slots.values()
    )
    summary = {
        "system_id": a.system_id,
        "api_slots_listed": len(slots),
        "slot_kinds": dict(kinds),
        "overlapping_field_slots": sum(1 for v in slots.values() if v["permit_is_for_overlapping_field"]),
        "screenshot_slots_compared": n,
        "agree_pct": round(100 * tally["agree"] / n, 1) if n else None,
        "mismatches": mismatches,
    }
    write_json(out / "summary.json", summary)
    for k, v in summary.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
