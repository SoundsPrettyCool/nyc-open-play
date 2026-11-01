"""Step G: check that park-level "X of N soccer fields free" counts are trustworthy.

For every park and 30-minute slot covered by the permit feed:
    N = active soccer-capable fields at the park (Athletic Facilities)
    B = distinct permit labels at the park overlapping the slot that occupy a
        soccer-type surface (rule below)
B > N is impossible on the ground, so it marks slots where our counts are off.

Surface rule:
    * soccer permits always count (Parks permitted soccer there, so it's soccer-capable)
    * other sports count only if the label names a soccer-type surface
      (soccer / football / multi-purpose / mppa / turf / futsal)
    * a bare "field" label counts only for field sports (football, lacrosse, rugby, frisbee)

One permit row can list several locations ("A: Soccer-01 ,A: Soccer-02"); each counts.
Half-field labels were checked and are negligible (1 label in the whole feed).

Reuses data downloaded by step F (run `step_f_events.py` first).

    python validation/step_g_counting.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from rapidfuzz import fuzz, process

from common import OUT, write_csv, write_json

SLOT = timedelta(minutes=30)
SOCCER_SURFACE = re.compile(r"soccer|football|multi[ -]?purpose|mppa|turf|futsal", re.I)
FIELD_WORD = re.compile(r"\bfield\b", re.I)
FIELD_SPORTS = re.compile(r"soccer|football|lacrosse|rugby|frisbee", re.I)
# Split multi-location rows on ',' or ';' that is followed by another "Park: label" segment.
LOCATION_SPLIT = re.compile(r"\s*[;,]\s*(?=[^,;]+:)")


def norm(s):
    s = (s or "").lower().replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def is_soccer_field(r):
    return any(str(r.get(k)).lower() == "true" for k in ("regulation_soccer", "nonregulation_soccer"))


def occupies_soccer_surface(sport: str, label: str) -> bool:
    if "soccer" in sport.lower():
        return True
    if SOCCER_SURFACE.search(label):
        return True
    return bool(FIELD_WORD.search(label) and FIELD_SPORTS.search(sport))


def split_locations(event_location: str) -> list[tuple[str, str]]:
    out = []
    for part in LOCATION_SPLIT.split(event_location):
        park, _, label = part.partition(":")
        if label.strip():
            out.append((park.strip(), label.strip()))
    return out


def slots(start: datetime, end: datetime):
    t = start.replace(minute=(start.minute // 30) * 30, second=0, microsecond=0)
    while t < end:
        yield t
        t += SLOT


class ParkMatcher:
    """Permit park name -> gispropnum. Official names (Parks Properties) win over Permit Areas aliases."""

    def __init__(self, props, areas, prefer: set[str]):
        self.primary, self.secondary = defaultdict(set), defaultdict(set)
        for p in props:
            for k in ("signname", "name311"):
                if p.get(k):
                    self.primary[norm(p[k])].add(p["gispropnum"])
        for a in areas:
            if a.get("propertyname") and a.get("gispropnum"):
                self.secondary[norm(a["propertyname"])].add(a["gispropnum"])
        self.keys = list(self.primary)
        self.prefer = prefer

    def _lookup(self, n):
        return self.primary.get(n) or self.secondary.get(n) or set()

    def match(self, name: str) -> str | None:
        n = norm(name)
        cands = self._lookup(n)
        if not cands:
            for part in re.split(r"\s*[/(]\s*", name):  # "A / B", "Park (School)"
                cands = self._lookup(norm(part.strip(") ")))
                if cands:
                    break
        if not cands:
            b = process.extractOne(n, self.keys, scorer=fuzz.token_set_ratio)
            cands = self.primary[b[0]] if b and b[1] >= 95 else set()
        if len(cands) > 1:
            cands = (cands & self.prefer) or cands
        return next(iter(cands)) if len(cands) == 1 else None


def main():
    load = lambda k: json.loads((OUT / "f" / f"{k}.json").read_text())  # noqa: E731
    events, props, areas, fields = load("events"), load("props"), load("areas"), load("fields")

    n_active = Counter(r["gispropnum"] for r in fields if is_soccer_field(r) and r.get("featurestatus") == "Active")
    n_any = Counter(r["gispropnum"] for r in fields if is_soccer_field(r))
    park_name = {p["gispropnum"]: p.get("signname") for p in props}
    matcher = ParkMatcher(props, areas, prefer=set(n_any))

    occ = defaultdict(set)  # (park, slot) -> {labels}
    labels_seen = defaultdict(set)  # park -> every soccer-surface label seen
    counted, multi_rows, skipped, unmatched = 0, 0, Counter(), Counter()
    for e in events:
        locs = split_locations(e["event_location"])
        multi_rows += len(locs) > 1
        start = datetime.fromisoformat(e["start_date_time"][:19])
        end = datetime.fromisoformat(e["end_date_time"][:19])
        for park, label in locs:
            if not occupies_soccer_surface(e["event_name"], label):
                skipped[e["event_name"]] += 1
                continue
            pid = matcher.match(park)
            if not pid:
                unmatched[park] += 1
                continue
            counted += 1
            labels_seen[pid].add(label)
            for t in slots(start, end):
                occ[(pid, t)].add(label)

    def classify(n, b):
        return "no_active_fields" if n == 0 else "over" if b > n else "full" if b == n else "some_free"

    def prime(t):  # weekends 9am-6pm, weekdays 5-9pm
        return (t.weekday() >= 5 and 9 <= t.hour < 18) or (t.weekday() < 5 and 17 <= t.hour < 21)

    allc, primec, per_park = Counter(), Counter(), defaultdict(Counter)
    for (pid, t), labs in occ.items():
        c = classify(n_active[pid], len(labs))
        allc[c] += 1
        per_park[pid][c] += 1
        per_park[pid]["slots"] += 1
        if prime(t):
            primec[c] += 1

    pct = lambda c: {k: round(100 * v / sum(c.values()), 1) for k, v in sorted(c.items())} | {"slots": sum(c.values())}  # noqa: E731

    problems = []
    for pid, c in per_park.items():
        bad = c["over"] + c["no_active_fields"]
        if not bad:
            continue
        mx = max(len(v) for (p, _), v in occ.items() if p == pid)
        problems.append({
            "gispropnum": pid, "park": park_name.get(pid, ""), "active_fields_N": n_active[pid],
            "all_soccer_fields_in_dataset": n_any[pid], "distinct_labels_in_permits": len(labels_seen[pid]),
            "max_concurrent_B": mx, "bad_slot_pct": round(100 * bad / c["slots"], 1), "bad_slots": bad,
            "likely_reason": (
                "no soccer fields in dataset" if n_any[pid] == 0
                else "soccer fields all inactive/closed in dataset" if n_active[pid] == 0
                else "permits use more surfaces than dataset lists"
            ),
            "suggested_N_override": max(n_active[pid], len(labels_seen[pid])),
            "labels": " | ".join(sorted(labels_seen[pid])[:25]),
        })
    problems.sort(key=lambda r: -r["bad_slots"])
    total_bad = sum(p["bad_slots"] for p in problems)

    summary = {
        "location_entries_counted": counted,
        "permit_rows_listing_multiple_locations": multi_rows,
        "location_entries_skipped_not_soccer_surface": sum(skipped.values()),
        "skipped_by_sport_top": dict(skipped.most_common(6)),
        "location_entries_unmatched_park": sum(unmatched.values()),
        "unmatched_park_names": dict(unmatched.most_common(20)),
        "parks_with_bookings": len(per_park),
        "all_slots_pct": pct(allc),
        "prime_time_slots_pct": pct(primec),
        "consistent_pct": round(100 * (allc["full"] + allc["some_free"]) / sum(allc.values()), 1),
        "problem_parks": len(problems),
        "top10_problem_parks_share_of_bad_slots_pct": round(100 * sum(p["bad_slots"] for p in problems[:10]) / total_bad, 1) if total_bad else 0,
    }
    out = OUT / "g"
    write_json(out / "summary.json", summary)
    write_csv(out / "problem_parks.csv", problems)
    for k, v in summary.items():
        print(f"{k}: {v}")
    print("\nProblem parks:")
    for p in problems:
        print(f"  {p['gispropnum']:6} {p['park'][:32]:32} N={p['active_fields_N']:<2} dataset={p['all_soccer_fields_in_dataset']:<2} "
              f"labels={p['distinct_labels_in_permits']:<3} maxB={p['max_concurrent_B']:<3} bad={p['bad_slot_pct']:>5}%  {p['likely_reason']}")
    print(f"\nWrote {out}/summary.json and problem_parks.csv")


if __name__ == "__main__":
    main()
