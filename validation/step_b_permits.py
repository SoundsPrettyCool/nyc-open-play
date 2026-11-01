"""Step B: fetch each soccer park's issued-permits page/spreadsheet.

Reads out/a/soccer_parks.csv. Each run writes a timestamped snapshot under
out/b/snapshots/<UTC timestamp>/ (reused by step E for churn diffs).

    python validation/step_b_permits.py --limit 5          # trial run
    python validation/step_b_permits.py                    # all parks, 3s apart
    python validation/step_b_permits.py --url-template 'https://www.nycgovparks.org/permits/field-and-court/issued/{park_id}/xlsx'

The URL shape below is a guess from the per-park URLs seen on the Parks site. Open
one park's issued-permits page in a browser first and set --url-template to match.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from common import OUT, USER_AGENT, Throttle, detect_format, parse_sheet, read_csv, session, write_csv

DEFAULT_TEMPLATE = "https://www.nycgovparks.org/permits/field-and-court/issued/{park_id}"
DOWNLOAD_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)


def download_links(html: str, base: str) -> list[str]:
    links = []
    for href in DOWNLOAD_HREF.findall(html):
        h = href.lower()
        if any(x in h for x in (".xlsx", ".xls", ".csv", "export", "download", "/xls", "/csv")):
            links.append(urljoin(base, href))
    return list(dict.fromkeys(links))


def robots_ok(s, url: str) -> tuple[bool, str]:
    root = "{0.scheme}://{0.netloc}/robots.txt".format(urlparse(url))
    try:
        r = s.get(root, timeout=30)
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        return rp.can_fetch(USER_AGENT, url), f"robots.txt HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return True, f"robots.txt unreadable: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--delay", type=float, default=3.0, help="seconds between requests")
    ap.add_argument("--limit", type=int, help="only the first N parks")
    ap.add_argument("--parks", help="comma-separated park IDs to fetch instead of all")
    ap.add_argument("--ignore-robots", action="store_true")
    a = ap.parse_args()

    parks = read_csv(OUT / "a" / "soccer_parks.csv")
    parks = [p for p in parks if p["park_id"]]
    if a.parks:
        want = set(a.parks.split(","))
        parks = [p for p in parks if p["park_id"] in want]
    if a.limit:
        parks = parks[: a.limit]

    s = session()
    sample = a.url_template.format(park_id=parks[0]["park_id"]) if parks else a.url_template
    allowed, note = robots_ok(s, sample)
    print(f"{note}; allowed for {sample}: {allowed}")
    if not allowed and not a.ignore_robots:
        raise SystemExit("robots.txt disallows this path. Stop and reconsider (or ask NYC Parks for a feed).")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snap = OUT / "b" / "snapshots" / ts
    raw = snap / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    throttle = Throttle(a.delay)
    log = []

    for i, p in enumerate(parks, 1):
        pid = p["park_id"]
        url = a.url_template.format(park_id=pid)
        rec = {"park_id": pid, "park_name": p["park_name"], "url": url}
        try:
            throttle.wait()
            t0 = time.monotonic()
            r = s.get(url, timeout=60, allow_redirects=True)
            rec.update(http_status=r.status_code, final_url=r.url, ms=int((time.monotonic() - t0) * 1000),
                       content_type=r.headers.get("content-type", ""), etag=r.headers.get("etag", ""),
                       last_modified=r.headers.get("last-modified", ""))
            data, fmt = r.content, detect_format(r.content, r.headers.get("content-type", ""))
            rec["page_format"] = fmt
            if fmt == "html" and r.ok:
                links = download_links(r.text, r.url)
                rec["download_links"] = " | ".join(links[:5])
                (raw / f"{pid}.page.html").write_bytes(data)
                if links:
                    throttle.wait()
                    d = s.get(links[0], timeout=60)
                    rec["download_status"] = d.status_code
                    dfmt = detect_format(d.content, d.headers.get("content-type", ""))
                    if d.ok and dfmt != "html":
                        data, fmt = d.content, dfmt
            rec["format"] = fmt
            rec["bytes"] = len(data)
            rec["sha256"] = hashlib.sha256(data).hexdigest()
            (raw / f"{pid}.{fmt}").write_bytes(data)
            header, records = parse_sheet(data, fmt) if r.ok else ([], [])
            rec["header"] = " | ".join(header)
            rec["rows"] = len(records)
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
        log.append(rec)
        print(f"[{i}/{len(parks)}] {pid} {rec.get('http_status', 'ERR')} {rec.get('format', '')} rows={rec.get('rows', '-')} {rec.get('error', '')}")

    write_csv(snap / "fetch_log.csv", log)
    (OUT / "b" / "LATEST").write_text(ts)
    ok = sum(1 for r in log if r.get("http_status") == 200)
    with_rows = sum(1 for r in log if r.get("rows"))
    headers = {r.get("header") for r in log if r.get("header")}
    print(f"\n{ok}/{len(log)} HTTP 200; {with_rows} with parsed permit rows; {len(headers)} distinct header layouts")
    print(f"Snapshot: {snap}")


if __name__ == "__main__":
    main()
