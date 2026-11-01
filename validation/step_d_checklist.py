"""Step D: generate a ground-truth checklist to compare against the NYC Parks
Availability Map (or the park itself).

We can't fetch nycgovparks.org from a server (CloudFront 403), so a person checks.
For each chosen park, this writes:
  * one comparison day: every permit our data has, to tick off against the map,
  * spot-check slots: our predicted park-level answer ("about X of N free").

Uses step F's downloaded data (re-run `step_f_events.py` first so it's fresh).

    python validation/step_d_checklist.py
    python validation/step_d_checklist.py --parks M011,M010,Q099,M165 --days 7
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from common import OUT
from step_g_counting import SLOT, ParkMatcher, is_soccer_field, occupies_soccer_surface, slots, split_locations

DEFAULT_PARKS = "M011,M010,Q099,M165"  # Chelsea (1 field), Central (7), Flushing Meadows (9), Baruch (problem park)
DAY_START, DAY_END = 7, 22  # hours considered for spot checks


def fmt_t(t: datetime) -> str:
    return t.strftime("%-I:%M%p").lower().replace(":00", "")


def answer(n: int, b: int) -> str:
    if n == 0:
        return "No active soccer fields listed"
    if b == 0:
        return f"No permits on record: all {n} look open"
    if b >= n:
        return f"Likely fully booked ({b} permits, {n} fields)"
    return f"About {n - b} of {n} fields have no permit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parks", default=DEFAULT_PARKS)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--spot-checks", type=int, default=8)
    ap.add_argument("--start", help="YYYY-MM-DD (default: tomorrow)")
    a = ap.parse_args()

    load = lambda k: json.loads((OUT / "f" / f"{k}.json").read_text())  # noqa: E731
    events, props, areas, fields = load("events"), load("props"), load("areas"), load("fields")
    n_active = Counter(r["gispropnum"] for r in fields if is_soccer_field(r) and r.get("featurestatus") == "Active")
    names = {p["gispropnum"]: p.get("signname") or p["gispropnum"] for p in props}
    matcher = ParkMatcher(props, areas, prefer=set(n_active))
    snapshot = datetime.fromtimestamp((OUT / "f" / "events.json").stat().st_mtime)

    start = (datetime.fromisoformat(a.start) if a.start
             else datetime.combine(datetime.now().date() + timedelta(days=1), datetime.min.time()))
    end = start + timedelta(days=a.days)
    wanted = a.parks.split(",")

    permits = defaultdict(list)  # park -> [(start, end, sport, label)]
    for e in events:
        s = datetime.fromisoformat(e["start_date_time"][:19])
        en = datetime.fromisoformat(e["end_date_time"][:19])
        if en <= start or s >= end:
            continue
        for park, label in split_locations(e["event_location"]):
            if not occupies_soccer_surface(e["event_name"], label):
                continue
            pid = matcher.match(park)
            if pid in wanted:
                permits[pid].append((s, en, e["event_name"], label))

    lines = [
        "# Step D — ground-truth checklist",
        "",
        f"Permit data snapshot: {snapshot:%Y-%m-%d %H:%M} · window {start:%a %b %-d} – {end - timedelta(days=1):%a %b %-d}",
        "",
        "**How to check** (about 10 minutes per park):",
        "1. Open the NYC Parks **Field & Court Permit Availability Map** in your browser and find the park.",
        "2. **Comparison day**: for each permit below, tick it if the map shows it. Then add any",
        "   permits the map shows that are missing here.",
        "3. **Spot checks**: does the map agree with our answer for that time?",
        "4. Please also note the URL of the park's permit page. We need the pattern to link to it.",
        "",
        "Mark each box `[x]` (matches) or `[!]` (doesn't), and add a note.",
        "",
        "⚠ About 11% of permits in the feed have an end time at or before the start time",
        "(e.g. 1pm–12pm). We can't tell the real end time, and our counts currently ignore",
        "these permits. For each ⚠ row, write down the time the map shows.",
        "",
    ]
    for pid in wanted:
        ps = sorted(permits.get(pid, []))
        n = n_active[pid]
        lines += [f"## {names.get(pid, pid)} (`{pid}`): N = {n} active soccer fields in dataset", ""]
        if not ps:
            lines += ["No soccer-surface permits in the window. Check that the map also shows none.", ""]
            continue
        # Comparison day = busiest day in the window
        by_day = Counter(s.date() for s, *_ in ps)
        day = max(by_day, key=lambda d: (by_day[d], d.weekday() >= 5))
        lines += [f"### Comparison day: {day:%A %b %-d} ({by_day[day]} permits)", "",
                  "| ✓ | Time | Sport | Label |", "|---|---|---|---|"]
        for s, en, sport, label in ps:
            if s.date() == day:
                bad = " ⚠ **end ≤ start: what time does the map show?** ____" if en <= s else ""
                lines.append(f"| [ ] | {fmt_t(s)}–{fmt_t(en)}{bad} | {sport} | {label} |")
        lines += ["", "Permits on the map but missing here: ________", ""]

        # Spot checks: spread across states (booked / some free / none) and days
        occ = defaultdict(set)
        for s, en, _, label in ps:
            for t in slots(s, en):
                occ[t].add(label)
        candidates = []
        t = start
        while t < end:
            if DAY_START <= t.hour < DAY_END:
                b = len(occ.get(t, ()))
                state = "none" if b == 0 else "full" if b >= n else "some"
                candidates.append((t, b, state))
            t += SLOT
        picks, used_days = [], Counter()
        for state in ("full", "some", "none") * a.spot_checks:
            pool = [c for c in candidates if c[2] == state and c not in picks
                    and c[0].minute == 0 and used_days[c[0].date()] < 2]
            if pool and len(picks) < a.spot_checks:
                c = pool[len(pool) // 2]
                picks.append(c)
                used_days[c[0].date()] += 1
        lines += ["### Spot checks", "", "| ✓ | When | Our answer | Permits we have |", "|---|---|---|---|"]
        for t, b, _ in sorted(picks):
            labs = ", ".join(sorted(occ.get(t, ()))) or "—"
            lines.append(f"| [ ] | {t:%a %b %-d} {fmt_t(t)} | {answer(n, b)} | {labs} |")
        lines += ["", "Notes: ________", ""]

    out = OUT / "d" / "checklist.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
