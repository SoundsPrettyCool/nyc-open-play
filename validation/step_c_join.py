"""Step C: score how well permit field labels join to Open Data soccer fields.

Uses out/a/soccer_fields.csv and the latest (or given) step-B snapshot.

    python validation/step_c_join.py
    python validation/step_c_join.py --label-col "Field" --snapshot 20261101T120000Z
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from rapidfuzz import fuzz, process

from common import OUT, normalize_label, parse_sheet, pick_column, read_csv, write_csv, write_json

LABEL_PATTERNS = (r"^field$", r"field", r"facility", r"location", r"site")
FUZZY_THRESHOLD = 85


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", help="snapshot timestamp under out/b/snapshots (default: LATEST)")
    ap.add_argument("--label-col", help="permit-sheet column holding the field label")
    ap.add_argument("--threshold", type=int, default=FUZZY_THRESHOLD)
    a = ap.parse_args()

    ts = a.snapshot or (OUT / "b" / "LATEST").read_text().strip()
    snap = OUT / "b" / "snapshots" / ts
    log = read_csv(snap / "fetch_log.csv")
    fields = read_csv(OUT / "a" / "soccer_fields.csv")

    by_park = defaultdict(list)
    for f in fields:
        by_park[f["_park_id"]].append(f)
    all_names = {(f["_park_id"], f["_field_name"]): normalize_label(f["_field_name"], f["_park_name"]) for f in fields}

    matches, unmatched = [], []
    header_layouts = Counter()
    label_cols_used = Counter()
    parks_with_rows = 0

    for rec in log:
        pid, fmt = rec["park_id"], rec.get("format")
        path = snap / "raw" / f"{pid}.{fmt}"
        if rec.get("http_status") != "200" or not fmt or not path.exists():
            continue
        header, rows = parse_sheet(path.read_bytes(), fmt)
        if not rows:
            continue
        parks_with_rows += 1
        header_layouts[" | ".join(header)] += 1
        label_col = a.label_col or pick_column(header, LABEL_PATTERNS)
        label_cols_used[label_col] += 1
        if not label_col:
            continue

        park_fields = by_park.get(pid, [])
        park_name = park_fields[0]["_park_name"] if park_fields else rec.get("park_name", "")
        candidates = {normalize_label(f["_field_name"], park_name): f["_field_name"] for f in park_fields}
        exact = {f["_field_name"].strip().lower(): f["_field_name"] for f in park_fields}

        for label, n in Counter(r.get(label_col, "") for r in rows).items():
            if not label:
                continue
            norm = normalize_label(label, park_name)
            m = {"park_id": pid, "park_name": park_name, "permit_label": label, "normalized": norm, "permit_rows": n}
            if label.strip().lower() in exact:
                m.update(method="exact", field=exact[label.strip().lower()], score=100)
            elif norm in candidates:
                m.update(method="normalized", field=candidates[norm], score=100)
            else:
                best = process.extractOne(norm, list(candidates), scorer=fuzz.token_set_ratio) if candidates else None
                if best and best[1] >= a.threshold:
                    m.update(method="fuzzy", field=candidates[best[0]], score=round(best[1]))
                else:
                    # Does it match a field in some *other* park? Signals an ID mismatch.
                    others = {k: v for k, v in all_names.items() if k[0] != pid}
                    other = process.extractOne(norm, others, scorer=fuzz.token_set_ratio) if others else None
                    m.update(method="none", field="", score=round(best[1]) if best else 0,
                             best_in_park=candidates.get(best[0], "") if best else "",
                             best_other_park=f"{other[2][0]}: {other[2][1]} ({round(other[1])})" if other else "")
            (matches if m["method"] != "none" else unmatched).append(m)

    labels = matches + unmatched
    by_method = Counter(m["method"] for m in labels)
    rows_total = sum(m["permit_rows"] for m in labels)
    rows_matched = sum(m["permit_rows"] for m in matches)
    fetched = len(log)
    ok = sum(1 for r in log if r.get("http_status") == "200")
    soccer_fields_hit = {(m["park_id"], m["field"]) for m in matches}

    def pct(x, y):
        return round(100 * x / y, 1) if y else 0.0

    summary = {
        "snapshot": ts,
        "parks_requested": fetched,
        "parks_http_200_pct": pct(ok, fetched),
        "parks_with_parsed_rows_pct": pct(parks_with_rows, fetched),
        "distinct_labels": len(labels),
        "labels_by_method": dict(by_method),
        "labels_matched_pct": pct(len(matches), len(labels)),
        "permit_rows_matched_pct": pct(rows_matched, rows_total),
        "soccer_fields_seen_in_permits": len(soccer_fields_hit),
        "soccer_fields_total": len(fields),
        "label_columns_used": {str(k): v for k, v in label_cols_used.items()},
        "header_layouts": dict(header_layouts.most_common(10)),
    }
    # Note: unmatched labels include non-soccer facilities (courts, ballfields without
    # soccer). Review unmatched.csv by hand before reading labels_matched_pct as a verdict.
    park_ok = summary["parks_http_200_pct"] >= 85
    label_ok = summary["permit_rows_matched_pct"] >= 85
    summary["verdict"] = (
        "GO: IDs resolve and labels auto-map; handle the rest with an override table" if park_ok and label_ok
        else "GO (park-level): IDs resolve but labels need mapping" if park_ok
        else "BLOCKED: park IDs don't line up; build a park crosswalk first"
    )
    write_csv(OUT / "c" / "matches.csv", matches)
    write_csv(OUT / "c" / "unmatched.csv", sorted(unmatched, key=lambda m: -m["permit_rows"]))
    write_json(OUT / "c" / "summary.json", summary)
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"\nWrote {OUT / 'c'}/ (matches.csv, unmatched.csv, summary.json)")


if __name__ == "__main__":
    main()
