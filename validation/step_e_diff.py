"""Step E: diff two step-B snapshots to measure permit churn.

Run step B on a schedule (e.g. twice a day for a week), then:

    python validation/step_e_diff.py                  # oldest vs newest snapshot
    python validation/step_e_diff.py OLD_TS NEW_TS
"""

from __future__ import annotations

import sys
from collections import Counter

from common import OUT, parse_sheet, read_csv, write_csv


def load(ts):
    snap = OUT / "b" / "snapshots" / ts
    out = {}
    for rec in read_csv(snap / "fetch_log.csv"):
        path = snap / "raw" / f"{rec['park_id']}.{rec.get('format')}"
        if rec.get("http_status") == "200" and path.exists():
            header, rows = parse_sheet(path.read_bytes(), rec["format"])
            out[rec["park_id"]] = (rec.get("sha256"), header, {tuple(sorted(r.items())) for r in rows})
    return out


def main():
    snaps = sorted(p.name for p in (OUT / "b" / "snapshots").iterdir() if p.is_dir())
    old_ts, new_ts = (sys.argv[1], sys.argv[2]) if len(sys.argv) == 3 else (snaps[0], snaps[-1])
    old, new = load(old_ts), load(new_ts)
    report, totals = [], Counter()
    for pid in sorted(set(old) | set(new)):
        o, n = old.get(pid), new.get(pid)
        if not o or not n:
            report.append({"park_id": pid, "change": "missing in old" if not o else "missing in new"})
            continue
        added, removed = n[2] - o[2], o[2] - n[2]
        totals.update(added=len(added), removed=len(removed), changed_files=int(o[0] != n[0]),
                      header_changed=int(o[1] != n[1]))
        if added or removed or o[1] != n[1]:
            report.append({"park_id": pid, "change": "rows", "added": len(added), "removed": len(removed),
                           "header_changed": o[1] != n[1],
                           "sample_removed": str(dict(next(iter(removed))))[:300] if removed else "",
                           "sample_added": str(dict(next(iter(added))))[:300] if added else ""})
    write_csv(OUT / "e" / f"diff_{old_ts}_{new_ts}.csv", report)
    print(f"{old_ts} -> {new_ts}: parks compared={len(set(old) & set(new))} {dict(totals)}")
    print("Look at sample_removed: deleted rows vs. a status column flipping tells you how revocations appear.")


if __name__ == "__main__":
    main()
