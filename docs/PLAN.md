# Soccer Open Play — Plan

Goal: tell a user whether an NYC park soccer field has **no permit on record** for a
given date/time (i.e. likely open play), or which kind of permit is on it and until when.

> **Updated 2026-11-01 after validation:** see [VALIDATION_FINDINGS.md](VALIDATION_FINDINGS.md).
> nycgovparks.org blocks automated clients (CloudFront 403). The primary permit source is
> now the official NYC Open Data feed **NYC Permitted Event Information (`tvpp-9vvx`)**.
> Its trade-offs: no permittee names, and a horizon of about 1 month. Sections below
> are updated where that changes the design.

Decisions so far:

| Question | Answer |
|---|---|
| Audience | Public, aiming to grow |
| Interface | Simple web page (with map) |
| Query shape | Both: yes/no for a slot, and free windows over a day/week |
| Coverage | All of NYC |
| Backend language | Python (tentative, confirm) |

Core principle: **user requests never hit upstream sources.** A background ingest job
pulls permits from the Open Data API into our DB daily; the web app reads only from the DB.

---

## 1. Data sources

| Source | What | Status |
|---|---|---|
| NYC Open Data "Athletic Facilities" (`qnem-b8re`) | 410 soccer fields (`regulation_soccer` OR `nonregulation_soccer`), park ID `gispropnum`, field ID `system`, `featurestatus`, WGS84 multipolygons | **Confirmed** |
| NYC Open Data "NYC Permitted Event Information" (`tvpp-9vvx`) | Approved Parks sports permits, ~1 month ahead, updated daily. No permittee names. | **Confirmed: primary permit source** |
| NYC Open Data "Parks Properties" (`enfh-gkve`) | Park names (`signname`, `name311`) → `gispropnum`; park boundaries | **Confirmed** |
| NYC Open Data "Parks Permit Areas" (`c5vm-g2dk`) | Extra park-name aliases | Confirmed (`cemsid` not useful for fields) |
| NYC Parks issued-permits spreadsheets / Availability Map | Season-long data, permittee names | **Blocked (CloudFront 403)**. Not used. |

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

**Status (2026-11-01):** A done. B blocked (CloudFront 403). C was replaced by
**F** (`step_f_events.py`), which joins the official `tvpp-9vvx` feed: 64% of soccer
permits auto-match, and 265 distinct locations go into a manual map. **Verdict: GO.**
D and E are still to do. Details are in [VALIDATION_FINDINGS.md](VALIDATION_FINDINGS.md).

Go / no-go:

- ≥85–90% park IDs resolve and labels auto-map → **go**, manual override table for the rest.
- Park IDs match, labels mostly don't → **go**, answer at park level until labels are mapped.
- Park IDs don't line up → build a park crosswalk first (Parks site park list, join on name/geometry).

## 3. Architecture

```
[Ingest job, daily] --(Socrata API)--> NYC Open Data (tvpp-9vvx, qnem-b8re, enfh-gkve)
      | raw JSON snapshots -> object storage (re-parseable, diffable)
      v
[Postgres + PostGIS + pg_trgm] <-- [FastAPI] <-- [Web UI + MapLibre] (CDN in front)
```

- **Python**: requests, rapidfuzz. **FastAPI** for the API.
- **Postgres**: PostGIS (geometry is already WGS84, so no reprojection), `pg_trgm` for
  fuzzy park search, `tstzrange` + GiST for overlap, `range_agg`/multiranges for free windows.
- No Redis initially; Postgres + CDN caching suffices.
- Frontend: light React/Vite or server-rendered + htmx.
- Hosting: one app container, one scheduled worker, managed Postgres.

Ingest: pull `tvpp-9vvx` (sports only) a few times a day, since it's cheap and official,
using a Socrata app token. Keep each snapshot. Replace the permit window wholesale on
each pull, so revoked permits disappear. Alert on new unmapped `event_location` labels,
and on a sudden drop in row count.

### Data model

- `park` (gispropnum, name, borough, aliases[], centroid, boundary MultiPolygon 4326)
- `field` (system, gispropnum, sports[], primary_sport, surface, lit, dimensions, geom 4326, featurestatus)
- `location_map` (event_location → field system, method: tier1/tier2/tier3/manual, verified)
- `source_snapshot` (dataset, fetched_at, row_count, sha256, blob_key)
- `permit` (event_id, field_system nullable, event_location, sport, youth/adult, during tstzrange, snapshot_id)
- `closure` (field_system, during, reason, source). Seeded from `featurestatus`.

GiST indexes on geometries and `permit.during`. Permits for **all sports** on a field
count as bookings, because the surface is shared.

### Answers are three-state

1. **No permit on record** (never "available")
2. **Permitted**: sport + youth/adult + until when (the permittee's name isn't published)
3. **Unknown**: stale data, unmapped field, field closed/inactive, or beyond the ~1-month horizon

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
- All-NYC soccer fields, scheduled Open Data ingest, reviewed location map (265 rows).
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

Answered by validation: column names / soccer marker / park ID (A); geometry is WGS84
multipolygons; Parks Properties shares `gispropnum`; the scraping question is moot
because we now use the official feed.

1. Does `tvpp-9vvx` drop revoked permits promptly? (E: run daily for a week, diff.)
2. Are `tvpp-9vvx` times America/New_York local? (Almost certainly. Confirm once.)
3. Partial-field (half-field) or multi-field permits? Some labels hint at this, e.g. `Soccer-01 E`, `Soccer Full Field`.
4. Does a permit for another sport on the same surface block soccer? (Assume yes.)
5. Is the ~1-month horizon acceptable? Season-long data would need NYC Parks to cooperate (email / FOIL).
6. What to show between seasons?
7. Are field names/numbers visible on the ground?
8. Satellite view in MVP? (Depends on imagery terms.)
9. Python confirmed, or TypeScript end to end?

## 7. Effort estimate (if validation is clean)

| Piece | Effort |
|---|---|
| Validation scripts | 1–3 days |
| Crawler + parser + ingest | 1–2 weeks (most of the risk) |
| API + DB | 3–5 days |
| Web UI + map | 1–2 weeks |
| Hardening (monitoring, overrides, admin) | ongoing |

≈ 4–6 weeks part-time for a solid MVP. The code is simple; the data is the hard part.
