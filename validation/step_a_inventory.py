"""Step A: inventory the Athletic Facilities dataset (qnem-b8re).

Discovers columns, how soccer is marked, the park-ID column, field-name column and
geometry, then writes the soccer subset. Column guesses can be overridden.

    python validation/step_a_inventory.py
    python validation/step_a_inventory.py --soccer-col soccer --park-col gispropnum --name-col signname
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter

from common import DATASET_ID, OUT, SOCRATA, session, write_csv, write_json

FALSY = {"", "no", "n", "false", "0", "none", "null"}
PARK_ID_RE = re.compile(r"^[BMQRX]\d{3}[A-Z0-9-]*$")  # borough letter + number, e.g. B073


def fetch_metadata(s):
    r = s.get(f"{SOCRATA}/api/views/{DATASET_ID}.json", timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_rows(s, page=50000):
    rows, offset = [], 0
    while True:
        r = s.get(
            f"{SOCRATA}/resource/{DATASET_ID}.json",
            params={"$limit": page, "$offset": offset, "$order": ":id"},
            timeout=120,
        )
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < page:
            return rows
        offset += page


def scalar(v):
    return v if isinstance(v, (str, int, float, bool)) or v is None else None


def geometry_report(rows, cols):
    rep = {}
    for c in cols:
        types, mags = Counter(), []
        for r in rows:
            g = r.get(c)
            if isinstance(g, dict):
                types[g.get("type", "?")] += 1
                coords = g.get("coordinates")
                while isinstance(coords, list) and coords and isinstance(coords[0], list):
                    coords = coords[0]
                if isinstance(coords, list) and coords and isinstance(coords[0], (int, float)):
                    mags.append(abs(coords[0]))
        if types:
            m = sorted(mags)[len(mags) // 2] if mags else None
            rep[c] = {
                "types": dict(types),
                "rows_with_geometry": sum(types.values()),
                "median_abs_x": m,
                "looks_like": None if m is None else ("WGS84 lon/lat" if m <= 180 else "projected (state plane feet?)"),
            }
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--soccer-col", help="column that marks soccer (truthy value = soccer)")
    ap.add_argument("--soccer-value", help="instead: substring that must appear in --soccer-col (e.g. 'soccer')")
    ap.add_argument("--park-col", help="column holding the park ID")
    ap.add_argument("--name-col", help="column holding the field name")
    ap.add_argument("--park-name-col", help="column holding the park name")
    ap.add_argument("--offline", action="store_true", help="reuse out/a/rows.json instead of fetching")
    a = ap.parse_args()
    out = OUT / "a"
    s = session()


    if a.offline:
        meta = json.loads((out / "metadata.json").read_text())
        rows = json.loads((out / "rows.json").read_text())
    else:
        meta = fetch_metadata(s)
        write_json(out / "metadata.json", meta)
        rows = fetch_rows(s)
        write_json(out / "rows.json", rows)

    columns = [
        {
            "fieldName": c.get("fieldName"),
            "name": c.get("name"),
            "type": c.get("dataTypeName"),
            "description": (c.get("description") or "").replace("\n", " ")[:300],
        }
        for c in meta.get("columns", [])
    ]
    write_csv(out / "columns.csv", columns)
    keys = sorted({k for r in rows for k in r})

    # --- how is soccer marked?
    soccer_named = [k for k in keys if "soccer" in k.lower()]
    soccer_valued = Counter()
    for r in rows:
        for k, v in r.items():
            if isinstance(v, str) and "soccer" in v.lower():
                soccer_valued[k] += 1
    soccer_col = a.soccer_col or (soccer_named[0] if soccer_named else (soccer_valued.most_common(1)[0][0] if soccer_valued else None))
    soccer_value = a.soccer_value or (None if soccer_col in soccer_named else "soccer")
    values_in_soccer_col = Counter(str(r.get(soccer_col)) for r in rows) if soccer_col else Counter()

    def is_soccer(r):
        v = r.get(soccer_col)
        if v is None:
            return False
        if soccer_value:
            return soccer_value.lower() in str(v).lower()
        return str(v).strip().lower() not in FALSY

    soccer = [r for r in rows if soccer_col and is_soccer(r)]

    # --- park ID column
    park_scores = {}
    for k in keys:
        vals = [scalar(r.get(k)) for r in rows if scalar(r.get(k)) is not None]
        if vals:
            park_scores[k] = sum(bool(PARK_ID_RE.match(str(v).strip())) for v in vals) / len(rows)
    park_col = a.park_col or max(park_scores, key=park_scores.get, default=None)

    # --- name columns
    name_col = a.name_col or next((k for k in keys if re.search(r"sign.?name|field.?name|^name$|facility.?name", k, re.I)), None)
    park_name_col = a.park_name_col or next((k for k in keys if re.search(r"park.?name|propname|^park$", k, re.I)), None)

    geo_cols = [c["fieldName"] for c in columns if (c["type"] or "").lower() in ("point", "polygon", "multipolygon", "line", "multiline", "location")]
    geo_cols += [k for k in keys if k not in geo_cols and any(isinstance(r.get(k), dict) and "coordinates" in r.get(k) for r in rows[:200])]
    geo = geometry_report(rows, geo_cols)

    soccer_fields = []
    for r in soccer:
        rec = {k: v for k, v in r.items() if scalar(v) is not None}
        rec["_park_id"] = (r.get(park_col) or "").strip() if park_col else ""
        rec["_field_name"] = r.get(name_col, "") if name_col else ""
        rec["_park_name"] = r.get(park_name_col, "") if park_name_col else ""
        rec["_has_geometry"] = any(isinstance(r.get(c), dict) for c in geo)
        soccer_fields.append(rec)
    first = ["_park_id", "_park_name", "_field_name", "_has_geometry"]
    write_csv(out / "soccer_fields.csv", soccer_fields, first + [k for k in keys if k not in first and k not in geo])

    parks = Counter((f["_park_id"], f["_park_name"]) for f in soccer_fields)
    write_csv(
        out / "soccer_parks.csv",
        [{"park_id": p, "park_name": n, "soccer_fields": c} for (p, n), c in sorted(parks.items())],
    )

    pid_pattern = Counter(re.sub(r"\d", "9", re.sub(r"[A-Z]", "A", f["_park_id"])) for f in soccer_fields)
    summary = {
        "total_rows": len(rows),
        "row_keys": keys,
        "soccer_named_columns": soccer_named,
        "columns_with_soccer_in_values": dict(soccer_valued.most_common(10)),
        "soccer_col_used": soccer_col,
        "soccer_match": f"substring '{soccer_value}'" if soccer_value else "truthy value",
        "top_values_in_soccer_col": dict(values_in_soccer_col.most_common(10)),
        "soccer_rows": len(soccer),
        "park_id_col_used": park_col,
        "park_id_col_scores": dict(sorted(park_scores.items(), key=lambda kv: -kv[1])[:8]),
        "park_id_patterns": dict(pid_pattern.most_common(10)),
        "soccer_rows_missing_park_id": sum(1 for f in soccer_fields if not f["_park_id"]),
        "distinct_soccer_parks": len(parks),
        "field_name_col_used": name_col,
        "park_name_col_used": park_name_col,
        "geometry": geo,
        "soccer_rows_without_geometry": sum(1 for f in soccer_fields if not f["_has_geometry"]),
    }
    write_json(out / "summary.json", summary)
    for k, v in summary.items():
        if k != "row_keys":
            print(f"{k}: {v}")
    print(f"\nrow keys: {', '.join(keys)}")
    print(f"\nWrote {out}/ (columns.csv, soccer_fields.csv, soccer_parks.csv, summary.json)")
    print("Check the guesses above; re-run with --offline and overrides if any are wrong.")


if __name__ == "__main__":
    main()
