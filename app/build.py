"""Build the static site's data from NYC Open Data + the NYC Parks slots API.

    python app/build.py                        # 2 weeks from today, all active soccer fields
    python app/build.py --limit 3 --cache DIR  # quick dev run: 3 fields, cache raw downloads

Outputs:
    app/site/data/index.json        park list for search + build metadata
    app/site/data/parks/<id>.json   one park: boundary, soccer fields, booked intervals

Sources:
    qnem-b8re (Open Data)  Athletic Facilities: soccer fields, IDs, geometry, status
    enfh-gkve (Open Data)  Parks Properties: park names + boundaries
    NYC Parks slots API  per-field availability (undocumented; see docs/VALIDATION_FINDINGS.md §7).
        Its URL is NOT hard-coded: set the NYC_PARKS_SLOTS_API_URL environment variable
        (a GitHub repository secret in CI). One request per field per week, sent politely:
        honest User-Agent, a fixed delay, retries only on 429/5xx, and a hard stop on 403.

Exit status is non-zero if the slots API refuses us or too many fields fail, so CI
doesn't publish a broken data set (the previous deployment stays live).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slots import NY, close_times, to_intervals  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "site" / "data"
SOCRATA = "https://data.cityofnewyork.us/resource"
SLOTS_API_ENV = "NYC_PARKS_SLOTS_API_URL"
UA = "nyc-open-play/0.1 (free open-play finder; https://github.com/SoundsPrettyCool/nyc-open-play)"
BOROUGHS = {"B": "Brooklyn", "M": "Manhattan", "Q": "Queens", "R": "Staten Island", "X": "Bronx"}
MAX_FAILURE_RATE = 0.2


class Refused(Exception):
    """The slots API answered 403: stop the whole run, don't retry or work around it."""


class SlotsError(Exception):
    """A field's request failed. The message never contains the API URL."""


def socrata(ds: str, params: dict, cache: Path | None, name: str) -> list[dict]:
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


def slots_api_url() -> str:
    """The slots API base URL, from the environment. Required: there is no default."""
    url = os.environ.get(SLOTS_API_ENV, "").strip()
    if not url:
        print(f"ERROR: set {SLOTS_API_ENV} to the NYC Parks slots API URL "
              "(on GitHub: Settings -> Secrets and variables -> Actions -> Secrets).", file=sys.stderr)
        sys.exit(3)
    if not url.startswith("https://"):
        print(f"ERROR: {SLOTS_API_ENV} must be an https:// URL.", file=sys.stderr)
        sys.exit(3)
    return url


def describe(r) -> str:
    """Short, URL-free description of an unexpected response: content type, server/CDN
    headers and the HTML title or first words, to tell a WAF block from an app error."""
    h = r.headers
    bits = [h.get("content-type", "no content-type")]
    for k in ("server", "x-cache", "via"):
        if h.get(k):
            bits.append(f"{k}={h[k]}")
    text = r.text or ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    snippet = " ".join((m.group(1) if m else re.sub(r"<[^>]+>", " ", text))[:100].split())
    if snippet:
        bits.append(f"page: {snippet!r}")
    return "; ".join(bits)


class SlotsClient:
    def __init__(self, url: str, delay: float, cache: Path | None):
        self.url, self.delay, self.cache, self._last = url, delay, cache, 0.0
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/json"})
        self.requests = 0

    def get(self, system_id: str, start: date) -> dict:
        path = self.cache / "slots" / f"{system_id}_{start}.json" if self.cache else None
        if path and path.exists():
            return json.loads(path.read_text())
        for attempt in range(3):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            r = self.s.get(self.url, params={"systemId": system_id, "startDate": start.isoformat()}, timeout=60)
            if r.status_code == 403:
                raise Refused(f"403 from slots API for {system_id}")
            if (r.status_code == 429 or r.status_code >= 500) and attempt < 2:
                time.sleep(self.delay * 2 ** (attempt + 1))
                continue
            if not r.ok:
                raise SlotsError(f"HTTP {r.status_code} ({describe(r)})")
            try:
                data = r.json()
            except ValueError:
                # e.g. an HTML bot-check or error page served with a 2xx status
                snippet = " ".join(r.text[:80].split())
                raise SlotsError(f"HTTP {r.status_code} but not JSON "
                                 f"({r.headers.get('content-type', 'no content-type')}): {snippet!r}") from None
            # A field with no bookings comes back without "availability" (just fieldName/close);
            # a wrong path comes back as {"error": ..., "message": ...} with HTTP 200.
            if not isinstance(data, dict) or "error" in data or not ({"availability", "fieldName", "close"} & set(data)):
                keys = sorted(data)[:5] if isinstance(data, dict) else type(data).__name__
                msg = f": {str(data.get('message'))[:80]!r}" if isinstance(data, dict) and data.get("message") else ""
                raise SlotsError(f"HTTP {r.status_code} unexpected JSON (keys: {keys}){msg}")
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
            return data
        raise SlotsError(f"HTTP {r.status_code}")


def round_coords(obj, nd):
    if isinstance(obj, (list, tuple)):
        return [round_coords(x, nd) for x in obj]
    return round(obj, nd) if isinstance(obj, float) else obj


def to_geojson(geom, simplify=0.0, nd=6):
    if geom is None or geom.is_empty:
        return None
    if simplify:
        geom = geom.simplify(simplify, preserve_topology=True)
    m = mapping(geom)
    return {"type": m["type"], "coordinates": round_coords(m["coordinates"], nd)}


def field_label(system_id: str) -> str:
    """'B073-ZN15-SOCCER-3' -> 'Soccer 3' (fallback when the API gives no fieldName)."""
    parts = system_id.split("-")
    return f"{parts[-2].title()} {parts[-1]}" if len(parts) >= 2 else system_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=2)
    ap.add_argument("--start", help="YYYY-MM-DD (default: today in New York)")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between slots API requests")
    ap.add_argument("--limit", type=int, help="only the first N active fields (dev runs)")
    ap.add_argument("--cache", type=Path, help="cache raw downloads here (dev runs)")
    a = ap.parse_args()

    api_url = slots_api_url()  # fail fast, before any downloads
    start = date.fromisoformat(a.start) if a.start else datetime.now(NY).date()
    weeks = [start + timedelta(days=7 * i) for i in range(a.weeks)]

    fields = socrata("qnem-b8re", {
        "$select": "system,gispropnum,featurestatus,surface_type,field_lighted,dimensions,multipolygon",
        "$where": "regulation_soccer = true OR nonregulation_soccer = true",
    }, a.cache, "fields")
    park_ids = sorted({f["gispropnum"] for f in fields if f.get("gispropnum")})

    names, boundaries = {}, defaultdict(list)
    for i in range(0, len(park_ids), 40):
        where = "gispropnum in(" + ",".join(f"'{x}'" for x in park_ids[i:i + 40]) + ")"
        for row in socrata("enfh-gkve", {"$select": "gispropnum,signname,name311,borough,multipolygon",
                                         "$where": where}, a.cache, f"props_{i}"):
            pid = row["gispropnum"]
            names.setdefault(pid, row)
            if row.get("multipolygon"):
                try:
                    boundaries[pid].append(shape(row["multipolygon"]))
                except Exception:  # noqa: BLE001
                    pass

    active = sorted((f for f in fields if f.get("featurestatus") == "Active"), key=lambda f: f["system"])
    if a.limit:
        active = active[: a.limit]
        park_ids = sorted({f["gispropnum"] for f in active})
    wanted = {f["system"] for f in active}

    client = SlotsClient(api_url, a.delay, a.cache)
    slot_data, failures = {}, {}
    try:
        for n, f in enumerate(active, 1):
            sid = f["system"]
            try:
                responses = [client.get(sid, w) for w in weeks]
                intervals, close, label = [], {}, None
                for resp in responses:
                    intervals += to_intervals(resp.get("availability") or {})
                    close.update(close_times(resp))
                    label = label or resp.get("fieldName")
                slot_data[sid] = {"intervals": intervals, "close": close, "label": label}
            except Refused:
                raise
            except SlotsError as e:
                failures[sid] = str(e)
            except Exception as e:  # noqa: BLE001  (network errors etc.; never include the URL)
                failures[sid] = f"{type(e).__name__} (network error)"
            if n % 25 == 0 or n == len(active):
                print(f"  slots: {n}/{len(active)} fields, {client.requests} requests, {len(failures)} failed", flush=True)
    except Refused as e:
        print(f"STOP: {e}. The slots API refused this client; not retrying.", file=sys.stderr)
        sys.exit(2)

    (OUT / "parks").mkdir(parents=True, exist_ok=True)
    for old in (OUT / "parks").glob("*.json"):
        old.unlink()

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    window = [weeks[0].isoformat(), (weeks[-1] + timedelta(days=6)).isoformat()]
    by_park = defaultdict(list)
    for f in fields:
        if f.get("gispropnum") in park_ids:
            by_park[f["gispropnum"]].append(f)

    index = []
    for pid in park_ids:
        info = names.get(pid, {})
        name = info.get("signname") or info.get("name311") or pid
        boundary = unary_union(boundaries[pid]) if boundaries.get(pid) else None
        geoms = {f["system"]: shape(f["multipolygon"]) for f in by_park[pid] if f.get("multipolygon")}
        anchor = boundary if boundary is not None else (unary_union(list(geoms.values())) if geoms else None)
        center = None
        if anchor is not None and not anchor.is_empty:
            pt = anchor.representative_point()
            center = [round(pt.x, 5), round(pt.y, 5)]

        park_fields = []
        for f in sorted(by_park[pid], key=lambda f: f["system"]):
            sid = f["system"]
            sd = slot_data.get(sid)
            if sid in wanted:
                data_status = "ok" if sd else "error"
            else:
                data_status = "not_checked" if f.get("featurestatus") == "Active" else "closed"
            park_fields.append({
                "id": sid,
                "name": (sd or {}).get("label") or field_label(sid),
                "status": f.get("featurestatus"),
                "data": data_status,
                "surface": f.get("surface_type"),
                "lit": str(f.get("field_lighted")).lower() == "true",
                "dimensions": f.get("dimensions"),
                "geometry": to_geojson(geoms.get(sid)),
                "close": (sd or {}).get("close", {}),
                "intervals": (sd or {}).get("intervals", []),
            })

        park = {
            "id": pid, "name": name, "borough": BOROUGHS.get((info.get("borough") or pid[:1]).upper(), ""),
            "center": center, "boundary": to_geojson(boundary, simplify=0.00003, nd=5),
            "generated_at": generated, "window": window, "fields": park_fields,
        }
        (OUT / "parks" / f"{pid}.json").write_text(json.dumps(park, separators=(",", ":")))
        index.append({
            "id": pid, "name": name, "aliases": sorted({info.get("name311")} - {None, name}),
            "borough": park["borough"], "center": center,
            "fields": sum(1 for f in park_fields if f["status"] == "Active"),
            # Compact availability for the search page: [field id, data status, [[start, end, state]]].
            "f": [[f["id"], f["data"], [[i["start"], i["end"], i["state"][0]] for i in f["intervals"]]]
                  for f in park_fields if f["status"] == "Active"],
        })

    index.sort(key=lambda p: p["name"].lower())
    meta = {
        "generated_at": generated, "window": window, "parks": len(index),
        "fields_checked": len(active), "fields_failed": len(failures), "slots_requests": client.requests,
        "failures": failures, "sources": ["qnem-b8re", "enfh-gkve", "NYC Parks slots API"],
    }
    (OUT / "index.json").write_text(json.dumps({"meta": meta, "parks": index}, separators=(",", ":")))

    size = sum(f.stat().st_size for f in OUT.rglob("*.json"))
    print(f"parks: {len(index)}  fields checked: {len(active)}  failed: {len(failures)}  "
          f"requests: {client.requests}  data: {size / 1e6:.2f} MB  window: {window[0]}..{window[1]}")
    if failures:
        # Reasons only (never the URL), so CI logs show why fields failed.
        print("failure reasons:")
        for reason, n in Counter(failures.values()).most_common():
            example = next(k for k, v in failures.items() if v == reason)
            print(f"  {n} x {reason}   e.g. {example}")
    if active and len(failures) / len(active) > MAX_FAILURE_RATE:
        print(f"FAIL: {len(failures)}/{len(active)} fields failed (> {MAX_FAILURE_RATE:.0%}); not publishing.",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
