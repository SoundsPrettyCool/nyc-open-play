"""Build the static site's data files from NYC Open Data.

    python app/build.py                 # fetch everything, write app/site/data/
    python app/build.py --cache DIR     # reuse/save raw downloads in DIR (handy for dev)

Outputs:
    app/site/data/index.json        park list for search + build metadata
    app/site/data/parks/<id>.json   one park: boundary, soccer fields, permits on record

Sources (all public Socrata APIs, no key needed; set SOCRATA_APP_TOKEN to raise limits):
    qnem-b8re  Athletic Facilities           soccer fields + geometry
    tvpp-9vvx  NYC Permitted Event Info      approved sports permits (~1 month ahead)
    enfh-gkve  Parks Properties              park names + boundaries
    c5vm-g2dk  Parks Permit Areas            extra park-name aliases
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from soccer import ParkMatcher, field_count, is_soccer_field, parse_permits  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "site" / "data"
SOCRATA = "https://data.cityofnewyork.us/resource"
BOROUGHS = {"B": "Brooklyn", "M": "Manhattan", "Q": "Queens", "R": "Staten Island", "X": "Bronx"}
UA = "soccer-open-play/0.1 (https://github.com/SoundsPrettyCool/soccer-open-play)"


def fetch(ds: str, params: dict, cache: Path | None, name: str) -> list[dict]:
    if cache and (cache / f"{name}.json").exists():
        return json.loads((cache / f"{name}.json").read_text())
    headers = {"User-Agent": UA}
    if os.environ.get("SOCRATA_APP_TOKEN"):
        headers["X-App-Token"] = os.environ["SOCRATA_APP_TOKEN"]
    rows, offset = [], 0
    while True:
        r = requests.get(f"{SOCRATA}/{ds}.json", params={**params, "$limit": 50000, "$offset": offset},
                         headers=headers, timeout=180)
        r.raise_for_status()
        batch = r.json()
        rows += batch
        if len(batch) < 50000:
            break
        offset += 50000
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{name}.json").write_text(json.dumps(rows))
    return rows


def round_coords(obj, nd=6):
    if isinstance(obj, (list, tuple)):
        return [round_coords(x, nd) for x in obj]
    return round(obj, nd) if isinstance(obj, float) else obj


def geom(g, simplify=0.0):
    """Socrata geometry dict -> rounded GeoJSON geometry (optionally simplified)."""
    try:
        s = shape(g)
    except Exception:  # noqa: BLE001
        return None
    if simplify:
        s = s.simplify(simplify, preserve_topology=True)
    out = mapping(s)
    return {"type": out["type"], "coordinates": round_coords(out["coordinates"], 5 if simplify else 6)}


def load_aliases() -> dict[str, str]:
    with (HERE / "park_aliases.csv").open(newline="") as f:
        return {r["permit_park_name"]: r["gispropnum"] for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, help="directory to cache raw downloads")
    a = ap.parse_args()

    fields = fetch("qnem-b8re", {"$select": "system,gispropnum,featurestatus,primary_sport,surface_type,field_lighted,"
                                 "dimensions,regulation_soccer,nonregulation_soccer,multipolygon"}, a.cache, "fields")
    events = fetch("tvpp-9vvx", {"$where": "event_type like 'Sport%'"}, a.cache, "events")
    props = fetch("enfh-gkve", {"$select": "gispropnum,signname,name311,borough"}, a.cache, "props")
    areas = fetch("c5vm-g2dk", {"$select": "gispropnum,propertyname"}, a.cache, "areas")

    soccer_fields = [f for f in fields if is_soccer_field(f)]
    by_park = defaultdict(list)
    for f in soccer_fields:
        by_park[f["gispropnum"]].append(f)
    matcher = ParkMatcher(props, areas, prefer=set(by_park), aliases=load_aliases())
    permits, unmatched = parse_permits(events, matcher)
    permits_by_park = defaultdict(list)
    for p in permits:
        permits_by_park[p.park].append(p)

    park_ids = sorted(set(by_park) | set(permits_by_park))
    info = {}
    for p in props:
        if p["gispropnum"] in park_ids and p["gispropnum"] not in info:
            info[p["gispropnum"]] = p

    # Boundaries for just the parks we need, in chunks (property rows can repeat per park).
    boundaries = defaultdict(list)
    for i in range(0, len(park_ids), 40):
        chunk = park_ids[i:i + 40]
        where = "gispropnum in(" + ",".join(f"'{x}'" for x in chunk) + ")"
        for row in fetch("enfh-gkve", {"$select": "gispropnum,multipolygon", "$where": where}, a.cache, f"bounds_{i}"):
            if row.get("multipolygon"):
                try:
                    boundaries[row["gispropnum"]].append(shape(row["multipolygon"]))
                except Exception:  # noqa: BLE001
                    pass

    (OUT / "parks").mkdir(parents=True, exist_ok=True)
    for old in (OUT / "parks").glob("*.json"):
        old.unlink()

    index = []
    starts = [p.start for p in permits]
    for pid in park_ids:
        pinfo = info.get(pid, {})
        name = pinfo.get("signname") or pinfo.get("name311") or pid
        fs = by_park.get(pid, [])
        active = [f for f in fs if f.get("featurestatus") == "Active"]
        ps = sorted(permits_by_park.get(pid, []), key=lambda p: (p.start, p.label))
        n = field_count(len(active), {p.label for p in ps if not p.unclear})
        boundary = unary_union(boundaries[pid]) if boundaries.get(pid) else None
        field_geoms = [shape(f["multipolygon"]) for f in fs if f.get("multipolygon")]
        anchor = boundary if boundary is not None else (unary_union(field_geoms) if field_geoms else None)
        center = None
        if anchor is not None and not anchor.is_empty:
            pt = anchor.representative_point()
            center = [round(pt.x, 5), round(pt.y, 5)]

        park = {
            "id": pid,
            "name": name,
            "borough": BOROUGHS.get((pinfo.get("borough") or pid[:1]).upper(), ""),
            "fields": n,
            "fields_in_dataset": len(fs),
            "active_in_dataset": len(active),
            "center": center,
            "boundary": geom(mapping(boundary), simplify=0.00003) if boundary is not None else None,
            "soccer_fields": {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": geom(f["multipolygon"]),
                     "properties": {"id": f["system"], "status": f.get("featurestatus"),
                                    "surface": f.get("surface_type"), "lit": str(f.get("field_lighted")).lower() == "true",
                                    "dimensions": f.get("dimensions")}}
                    for f in fs if f.get("multipolygon")
                ],
            },
            "permits": [p.to_json() for p in ps],
        }
        (OUT / "parks" / f"{pid}.json").write_text(json.dumps(park, separators=(",", ":")))
        aliases = sorted({pinfo.get("name311")} - {None, name})
        index.append({"id": pid, "name": name, "aliases": aliases, "borough": park["borough"],
                      "fields": n, "center": center, "permits": len(ps)})

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "permit_window": [min(starts).strftime("%Y-%m-%d"), max(starts).strftime("%Y-%m-%d")] if starts else None,
        "permits": len(permits),
        "permits_unclear_time": sum(p.unclear for p in permits),
        "unmatched_park_names": dict(Counter(unmatched).most_common()),
        "sources": ["qnem-b8re", "tvpp-9vvx", "enfh-gkve", "c5vm-g2dk"],
    }
    index.sort(key=lambda p: p["name"].lower())
    (OUT / "index.json").write_text(json.dumps({"meta": meta, "parks": index}, separators=(",", ":")))

    size = sum(f.stat().st_size for f in OUT.rglob("*.json"))
    print(f"parks: {len(index)}  permits: {len(permits)}  unclear: {meta['permits_unclear_time']}  "
          f"data size: {size / 1e6:.1f} MB")
    if unmatched:
        print("unmatched permit park names (add to app/park_aliases.csv):", meta["unmatched_park_names"])


if __name__ == "__main__":
    main()
