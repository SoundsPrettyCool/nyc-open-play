# Soccer Open Play — Plan

Goal: tell a user whether an NYC park soccer field has **no permit on record** for a
given date/time (i.e. likely open play), or who holds the permit and until when.

Decisions so far:

| Question | Answer |
|---|---|
| Audience | Public, aiming to grow |
| Interface | Simple web page (with map) |
| Query shape | Both: yes/no for a slot, and free windows over a day/week |
| Coverage | All of NYC |
| Backend language | Python (tentative, confirm) |

Core principle: **user requests never hit nycgovparks.org.** A background crawler
ingests every park's permits into our DB; the web app reads only from the DB.

---

## 1. Data sources

| Source | What | Status |
|---|---|---|
| NYC Open Data "Athletic Facilities" (`qnem-b8re`) | Fields, sports, park IDs, geometry (NY State Plane LI, EPSG:2263) | Column names unconfirmed |
| NYC Parks issued-permits spreadsheet per park (`nycgovparks.org/permits/field-and-court/issued/<park-id>/...`) | Current-season permits | Undocumented, may change |
| NYC Parks Field & Court Permit Availability Map | Possible JSON backend | Not yet inspected |
| NYC Open Data "Parks Properties" | Park boundaries for the map | Dataset ID to confirm |

## 2. Validation (before any app code)

Scripts live in [`validation/`](../validation/README.md).

- **A. Open Data inventory:** columns, how soccer is marked, park ID format, field
  names/status, geometry type (point vs polygon), whether WGS84 is already exposed.
- **B. Permit inventory:** for every soccer park ID, fetch the issued-permits URL;
  record HTTP status, format (xlsx/csv/html), headers, rows. Check `robots.txt`/ToS.
  Inspect the Availability Map in devtools for a JSON endpoint.
- **C. Join scoring:** % park IDs that resolve; % permit field labels matching an
  Open Data field (exact → normalized → fuzzy); list of unmatched labels. Do permits
  for other sports name the same physical surface?
- **D. Ground truth (manual):** 3 parks × ~10 slots vs. the Availability Map; spot-check
  ~10 transformed field geometries against aerial imagery.
- **E. Churn:** snapshot sheets twice daily for ~1 week, diff. Sets refresh cadence;
  shows whether revocations delete rows or change a status.

Go / no-go:

- ≥85–90% park IDs resolve and labels auto-map → **go**, manual override table for the rest.
- Park IDs match, labels mostly don't → **go**, answer at park level until labels are mapped.
- Park IDs don't line up → build a park crosswalk first (Parks site park list, join on name/geometry).

## 3. Architecture

```
[Crawler worker] --(rate-limited, conditional GET)--> nycgovparks.org
      | raw files -> object storage (re-parseable)
      v
[Postgres + PostGIS + pg_trgm] <-- [FastAPI] <-- [Web UI + MapLibre] (CDN in front)
```

- **Python**: openpyxl/pandas, rapidfuzz, pyproj. **FastAPI** for the API.
- **Postgres**: PostGIS (`ST_Transform` 2263→4326 at ingest), `pg_trgm` for fuzzy park
  search, `tstzrange` + GiST for overlap, `range_agg`/multiranges for free windows.
- No Redis initially; Postgres + CDN caching suffices.
- Frontend: light React/Vite or server-rendered + htmx.
- Hosting: one app container, one scheduled worker, managed Postgres.

Crawler: staggered 3–4×/day, a few seconds between requests, ETag/Last-Modified,
on-demand refresh of stale parks via a locked, rate-limited queue (never inline),
keep last good snapshot on parse failure, alert on parse-failure spikes.

### Data model

- `park` (id, name, borough, aliases[], centroid, boundary MultiPolygon 4326)
- `field` (id, park_id, open_data_id, name, sports[], surface, lit, geom 4326, status)
- `field_label_map` (park_id, permit_label → field_id, method, confidence, verified)
- `source_snapshot` (park_id, fetched_at, http_status, sha256, row_count, parse_ok, blob_key)
- `permit` (park_id, field_id nullable, raw_label, permittee, during tstzrange, status, snapshot_id)
- `closure` (field_id, during, reason, source)

GiST indexes on geometries and `permit.during`.

### Answers are three-state

1. **No permit on record** (never "available")
2. **Permitted**: permittee + until when
3. **Unknown**: stale data, unmapped field, or outside current season

Always show data freshness.

## 4. Map view

Purpose: let users **verify the place** is the one they mean.

- Park boundary; field footprints/markers labeled and colored by status at the
  selected time (color + pattern/label, not color alone); selected field highlighted;
  list ↔ map selection linked; "Open in Google/Apple Maps" per field.
- **MapLibre GL JS**. Basemap: **Protomaps PMTiles** self-hosted on object storage/CDN
  (no per-request cost, no key); hosted MapTiler/Stadia free tier as alternative.
  Do not use public OSM tile servers.
- Satellite toggle using free NYC/NYS orthoimagery if terms allow.
- API: `GET /parks/{id}/geo?at=<datetime>` → GeoJSON FeatureCollection with per-field
  status. Simplify boundaries at ingest (`ST_SimplifyPreserveTopology`).

## 5. MVP vs. later

**MVP**
- All-NYC soccer fields, scheduled crawler.
- Fuzzy park search with mini-map per result for disambiguation.
- Park page: per-field day timeline, slot check, map.
- Three-state answers, freshness stamps, "unofficial; fields may be closed" disclaimer.
- Admin view of unmapped labels and crawl health.

**Later**
- City-wide map with "near me" + clustering (vector tiles).
- Week view; alerts when a field frees up (mid-season revocations).
- User-reported closures/conditions; other sports; historical patterns.
- Off-season handling; PWA.
- Map-based admin tool: click the polygon a permit label refers to.

## 6. Open questions

1. Real column names, how soccer is marked, park ID format? (A)
2. Does the permit URL park ID equal the Open Data park ID? (B)
3. Permit sheet format: recurring permits expanded? cancelled rows included? local times?
4. Does the Availability Map have a JSON backend?
5. Partial-field (half-field) or multi-field permits?
6. Does a permit for another sport on the same surface block soccer? (Assume yes.)
7. Will NYC Parks provide an official feed? Does ToS forbid scraping? (Email / FOIL.)
8. What to show between seasons?
9. Field geometry: polygons or points?
10. Are field names/numbers visible on the ground?
11. Satellite view in MVP? (Depends on imagery terms.)
12. Does the park-boundary dataset share the Athletic Facilities park ID?
13. Python confirmed, or TypeScript end to end?

## 7. Effort estimate (if validation is clean)

| Piece | Effort |
|---|---|
| Validation scripts | 1–3 days |
| Crawler + parser + ingest | 1–2 weeks (most of the risk) |
| API + DB | 3–5 days |
| Web UI + map | 1–2 weeks |
| Hardening (monitoring, overrides, admin) | ongoing |

≈ 4–6 weeks part-time for a solid MVP. The code is simple; the data is the hard part.
