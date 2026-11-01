"""Step F: join official sports permits (NYC Open Data) to Athletic Facilities soccer fields.

Replaces steps B/C as the primary path: nycgovparks.org blocks automated clients
(CloudFront 403), but NYC Open Data publishes approved Parks sports permits in
"NYC Permitted Event Information" (tvpp-9vvx), updated daily, covering ~1 month ahead.

Join path:
    permit.event_location "Park Name: [Zone-]Sport-NN"
      -> park name -> gispropnum   (Parks Properties enfh-gkve + Parks Permit Areas c5vm-g2dk)
      -> soccer field in Athletic Facilities (qnem-b8re) by tiers:
           1. same sport token + number as the field's SYSTEM id
           2. unique number among the park's soccer-capable fields
           3. park has exactly one active soccer-capable field
Anything else is "ambiguous" or "unmatched" and needs the manual override table.

    python validation/step_f_events.py            # fetch + score
    python validation/step_f_events.py --offline  # reuse out/f/*.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from rapidfuzz import fuzz, process

from common import OUT, SOCRATA, session, write_csv, write_json

LOC = re.compile(r"^(?P<park>.+?):\s*(?P<rest>.+)$")
SPORT = re.compile(r"(soccer|football|baseball|softball|cricket|rugby|lacrosse|hockey|mppa)", re.I)
SYSTEM = re.compile(r"^([A-Z]+\d+[A-Z]?)(?:-(?:ZN\d+|\d+))?-([A-Z_ ]+)-(\d+)$")


def fetch_all(s, ds, **params):
    out, off = [], 0
    while True:
        r = s.get(f"{SOCRATA}/resource/{ds}.json", params={**params, "$limit": 50000, "$offset": off}, timeout=120)
        r.raise_for_status()
        batch = r.json()
        out += batch
        if len(batch) < 50000:
            return out
        off += 50000


def norm(s):
    s = (s or "").lower().replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def is_soccer(r):
    return any(str(r.get(k)).lower() == "true" for k in ("regulation_soccer", "nonregulation_soccer"))


def sys_key(system):
    m = SYSTEM.match(system or "")
    return (m.group(2).lower(), int(m.group(3))) if m else (None, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    out = OUT / "f"
    out.mkdir(parents=True, exist_ok=True)
    files = {"events": "tvpp-9vvx", "props": "enfh-gkve", "areas": "c5vm-g2dk", "fields": "qnem-b8re"}
    params = {
        "events": {"$where": "event_type like 'Sport%'"},
        "props": {"$select": "gispropnum,signname,name311,borough"},
        "areas": {"$select": "cemsid,gispropnum,propertyname"},
        "fields": {"$select": "system,gispropnum,featurestatus,primary_sport,regulation_soccer,nonregulation_soccer"},
    }
    data = {}
    s = session()
    for k, ds in files.items():
        p = out / f"{k}.json"
        if not a.offline:
            write_json(p, fetch_all(s, ds, **params[k]))
        data[k] = json.loads(p.read_text())

    soccer = [r for r in data["fields"] if is_soccer(r)]
    by_park = defaultdict(list)
    for r in soccer:
        by_park[r["gispropnum"]].append(r)
    soccer_parks = set(by_park)

    names = defaultdict(set)
    for p in data["props"]:
        for k in ("signname", "name311"):
            if p.get(k):
                names[norm(p[k])].add(p["gispropnum"])
    for ar in data["areas"]:
        if ar.get("propertyname") and ar.get("gispropnum"):
            names[norm(ar["propertyname"])].add(ar["gispropnum"])
    name_keys = list(names)

    def park_ids(name):
        n = norm(name)
        if n in names:
            return names[n]
        for part in re.split(r"\s*[/(]\s*", name):  # "A / B", "Park (School)"
            if norm(part.strip(") ")) in names:
                return names[norm(part.strip(") "))]
        b = process.extractOne(n, name_keys, scorer=fuzz.token_set_ratio)
        if b and b[1] >= 95 and names[b[0]] & soccer_parks:
            return names[b[0]] & soccer_parks
        return set()

    events = [e for e in data["events"] if "soccer" in e.get("event_name", "").lower()]
    loc_result = {}
    for loc in Counter(e["event_location"] for e in events):
        m = LOC.match(loc.split(";")[0])
        if not m:
            loc_result[loc] = ("unparsed", "", "")
            continue
        ids = park_ids(m["park"])
        if not ids:
            loc_result[loc] = ("park_unmatched", "", "")
            continue
        fs = [r for g in ids for r in by_park.get(g, [])]
        active = [r for r in fs if r.get("featurestatus") == "Active"] or fs
        sp = SPORT.search(m["rest"])
        nums = re.findall(r"\d+", m["rest"])
        key = (sp.group(1).lower() if sp else None, int(nums[-1]) if nums else None)
        tiers = [
            ("tier1_token_num", [r for r in fs if sys_key(r["system"]) == key]),
            ("tier2_num", [r for r in active if sys_key(r["system"])[1] == key[1]]),
            ("tier3_only_field", active),
        ]
        hit = next(((t, c[0]) for t, c in tiers if len(c) == 1), None)
        if hit:
            loc_result[loc] = (hit[0], hit[1]["system"], ",".join(sorted(ids)))
        else:
            loc_result[loc] = ("no_soccer_field" if not fs else "ambiguous", "", ",".join(sorted(ids)))

    loc_counts = Counter(e["event_location"] for e in events)
    by_tier = Counter()
    for loc, n in loc_counts.items():
        by_tier[loc_result[loc][0]] += n
    total = len(events)
    matched = sum(v for k, v in by_tier.items() if k.startswith("tier"))
    hit_fields = {loc_result[l][1] for l in loc_counts if loc_result[l][1]}
    active_soccer = [r for r in soccer if r.get("featurestatus") == "Active"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    starts = [datetime.fromisoformat(e["start_date_time"][:19]) for e in data["events"]]
    ranked = loc_counts.most_common()

    summary = {
        "sport_permits": len(data["events"]),
        "soccer_permits": total,
        "distinct_soccer_locations": len(loc_counts),
        "permits_by_tier_pct": {k: round(100 * v / total, 1) for k, v in sorted(by_tier.items())},
        "auto_matched_pct": round(100 * matched / total, 1),
        "locations_auto_matched": sum(1 for l in loc_counts if loc_result[l][1]),
        "active_soccer_fields": len(active_soccer),
        "active_soccer_fields_with_permits": sum(1 for r in active_soccer if r["system"] in hit_fields),
        "top_100_locations_cover_pct": round(100 * sum(c for _, c in ranked[:100]) / total, 1),
        "permit_start_horizon": {
            "past": sum(x < now for x in starts),
            "next_31_days": sum(now <= x < now + timedelta(days=31) for x in starts),
            "later": sum(x >= now + timedelta(days=31) for x in starts),
        },
    }
    write_json(out / "summary.json", summary)
    write_csv(
        out / "location_map.csv",
        [{"event_location": l, "permits": c, "result": loc_result[l][0], "system": loc_result[l][1],
          "gispropnum": loc_result[l][2]} for l, c in ranked],
    )
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"\nWrote {out}/location_map.csv (seed for the manual override table) and summary.json")


if __name__ == "__main__":
    main()
