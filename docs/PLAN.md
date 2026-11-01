# Soccer Open Play — Plan

Goal: tell a user whether **an NYC park has at least one soccer field with no permit on
record** at a given date/time, so they can show up for open play. Which field to use is
left to the player on site, or to the park's nycgovparks.org permit page, which we link.

> **Updated 2026-11-01.** Validation results are in [VALIDATION_FINDINGS.md](VALIDATION_FINDINGS.md).
> - nycgovparks.org blocks automated clients (CloudFront 403), so we use the official
>   NYC Open Data permit feed **`tvpp-9vvx`** instead.
> - Answers are **park-level**, not field-level. This removes the hard part (mapping
>   permits to exact fields): 92.4% of soccer permits map to a park automatically, and
>   a 10-row alias table covers the rest.

Decisions so far:

| Question | Answer |
|---|---|
| Audience | Public, aiming to grow |
| Interface | Simple web page (with map) |
| Granularity | **Park-level**: "X of N soccer fields free", not which field |
| Query shape | Both: yes/no for a slot, and free windows over a day/week |
| Coverage | All of NYC (215 parks with soccer fields) |
| Backend language | Python (tentative, confirm) |

Core principle: **user requests never hit upstream sources.** A background ingest job
pulls from the Open Data API into our DB; the web app reads only from the DB.

---

## 1. Data sources

| Source | Used for | Status |
|---|---|---|
| "Athletic Facilities" (`qnem-b8re`) | Count of **active** soccer fields per park (`regulation_soccer` OR `nonregulation_soccer`, `featurestatus = Active`), field polygons for the map | Confirmed |
| "NYC Permitted Event Information" (`tvpp-9vvx`) | Sports permits: park name + label in `event_location`, start/end, sport, youth/adult. ~1 month ahead, updated daily, no permittee names. | Confirmed: primary permit source |
| "Parks Properties" (`enfh-gkve`) | Park name → `gispropnum`; park boundary; search names | Confirmed |
| "Parks Permit Areas" (`c5vm-g2dk`) | Extra park-name aliases | Confirmed |
| nycgovparks.org | **Linked only** (per-park permit page for confirming the exact field). Never fetched by us. | Blocked for automated clients |

## 2. Validation status

Scripts are in [`validation/`](../validation/README.md); results are in [VALIDATION_FINDINGS.md](VALIDATION_FINDINGS.md).

| Step | Status |
|---|---|
| A. Open Data inventory | Done |
| B/C. Scrape nycgovparks.org permit sheets | Blocked (CloudFront 403). Dropped. |
| F. Permit feed → park join | Done: 92.4% of soccer permits auto-match a park; 10 park names need aliases |
| G. Park-level counting check | Done: **94.1%** of park-slots consistent; the 21 problem parks are fixed with a per-park `N` override |
| D. Ground truth | **Checklist ready** ([STEP_D_CHECKLIST.md](STEP_D_CHECKLIST.md)): 4 parks, Nov 2–8. Needs a person with a browser, because the map is on nycgovparks.org. |
| E. Churn | To do: pull `tvpp-9vvx` daily for a week and diff (do revoked permits disappear?) |

## 3. How an answer is computed

For park `P` and time window `T`:

1. `N` = active soccer-capable fields in `P`, from Athletic Facilities, or the park's
   `n_override` when it has one. The override is the larger of the dataset count and the
   distinct soccer-surface labels seen in permits; step G found 21 parks that need it.
2. `B` = **distinct permit labels** (the part of `event_location` after the colon, e.g.
   `North Meadow-Soccer-03`) at `P` that overlap `T` and are on a soccer-capable
   surface. That means soccer permits, plus other sports whose label names a soccer,
   football, multi-purpose, MPPA, turf or futsal surface; a bare "field" label counts
   only for field sports. One permit row can list several locations, separated by
   commas; count each.
3. `free = N − B`.

| Condition | Answer shown |
|---|---|
| `B = 0` | **"No permits on record: all N soccer fields look open"** |
| `0 < B < N` | **"About `free` of N soccer fields have no permit"** |
| `B ≥ N` | **"Likely fully booked"**. Never a negative number. Permit list shown. |
| `N = 0` (all inactive/closed) | **"No active soccer fields listed"** |
| Park unmapped, data stale, or `T` beyond the horizon | **"Unknown"**, with the reason |

Below every answer:
- the overlapping permits ("Youth soccer · Soccer-03 · until 12:00pm"),
- the data freshness ("Permits updated 6:10am today"),
- a link to the park's nycgovparks.org permit page for the exact field. The URL
  pattern still needs confirming in a browser.

The counts are approximate, mainly because the fields dataset sometimes undercounts a
park's surfaces (handled with `n_override`). The wording says "about", and the permit
list lets users judge for themselves.

**Free windows** for the day/week view: split the day into 30-minute slots, compute
`free` for each slot, and merge runs of slots where `free > 0`. Result: "Open play
likely 7–9am, 12–3pm".

## 4. Architecture

```
[Ingest job, a few times/day] --(Socrata API)--> NYC Open Data
      | raw JSON snapshots -> object storage (re-parseable, diffable)
      v
[Postgres + PostGIS + pg_trgm] <-- [FastAPI] <-- [Web UI + MapLibre] (CDN in front)
```

- **Python**: requests, rapidfuzz. **FastAPI** for the API.
- **Postgres**: PostGIS (geometry is already WGS84), `pg_trgm` for fuzzy park search,
  `tstzrange` + GiST for overlap queries.
- No Redis initially; Postgres + CDN caching suffices. With ~215 parks and ~1 month of
  permits, everything fits in memory, so per-park answers can also be precomputed.
- Frontend: light React/Vite or server-rendered + htmx.
- Hosting: one app container, one scheduled worker, managed Postgres.

**Ingest**
- Permits: pull `tvpp-9vvx` sports permits a few times a day, using a Socrata app
  token. Replace the permit window wholesale on each pull, so revoked permits disappear.
- Fields and parks: refresh weekly.
- Alerts: a new park name that doesn't map; a sudden drop in permit count; a failed pull.

### Data model

- `park` (gispropnum, name, borough, aliases[], centroid, boundary MultiPolygon 4326, permit_page_url, n_override nullable)
- `park_alias` (permit_park_name → gispropnum). Seeded with the 10 unmatched names.
- `field` (system, gispropnum, primary_sport, surface, lit, dimensions, geom 4326, featurestatus).
  Used for `N` and for map context only.
- `permit` (event_id, gispropnum, label, sport, youth/adult, during tstzrange, snapshot_id)
- `source_snapshot` (dataset, fetched_at, row_count, sha256, blob_key)

GiST index on `permit.during`.

## 5. Map view

Purpose: let users **verify the park** is the one they mean, and see where its soccer
fields are.

- The park boundary, plus its soccer field polygons drawn **neutrally** (no per-field
  status, because we don't know which field a permit is on). The park-level answer sits
  next to the map.
- "Open in Google/Apple Maps" for directions.
- **MapLibre GL JS**, with **Protomaps PMTiles** self-hosted on object storage/CDN as the
  basemap. A hosted MapTiler/Stadia free tier is the alternative. Don't use public OSM
  tile servers.
- Satellite toggle using free NYC/NYS aerial imagery if the terms allow. It helps people
  spot the fields.
- API: `GET /parks/{id}/geo` returns GeoJSON (boundary + fields). Simplify boundaries at
  ingest (`ST_SimplifyPreserveTopology`).

## 6. MVP vs. later

**MVP**
- All 215 parks with soccer fields; scheduled Open Data ingest; park alias table.
- Fuzzy park search with a mini-map per result, to tell similar names apart.
- Park page: the park-level answer for the chosen time, free windows for the day, the
  permit list, the map, and the nycgovparks.org link.
- Freshness stamps; disclaimer: "Unofficial. Based on permits on record. Fields may be
  closed or in informal use."
- Simple ops page: last ingest, unmapped park names.

**Later**
- City-wide map with "near me" (PostGIS distance) and "parks with open fields right now".
- Week view; alerts ("tell me if a field opens up at X on Saturday").
- User reports ("all fields were taken", "field closed") to correct counts.
- Field-level answers, if users ask for them: map permit labels to fields (we have
  64% automatic matching already, and the location map in `step_f_events.py` as a seed).
- Other sports; historical patterns ("usually free Sunday mornings"); off-season handling; PWA.

## 7. Open questions

Answered: column names, soccer marker, park ID; geometry is WGS84; Parks Properties
shares `gispropnum`; scraping is moot.

Also answered by step G: counting is consistent in 94.1% of park-slots, the 21 problem
parks get an `n_override`, and half-field permits are negligible.

1. **Real-world accuracy** (step D): does "about X free" match what's on the ground or on the Availability Map? The checklist is in [STEP_D_CHECKLIST.md](STEP_D_CHECKLIST.md).
1a. **11% of permits have end ≤ start** (findings §4d). Assume a default length, block to end of day, or answer "Unknown"? Decide after step D shows what the map says for those permits.
2. Does `tvpp-9vvx` drop revoked permits promptly? (E)
3. Are `tvpp-9vvx` times America/New_York local? (Almost certainly. Confirm once.)
4. Should `n_override` be recomputed automatically on each ingest (any park where permits ever exceed `N`), or reviewed by hand?
5. Is the ~1-month horizon acceptable? Season-long data would need NYC Parks to cooperate (email / FOIL).
6. What's the per-park nycgovparks.org permit-page URL pattern? (Check in a browser.)
7. What to show between seasons?
8. Satellite view in MVP? (Depends on imagery terms.)
9. Python confirmed, or TypeScript end to end?

## 8. Effort estimate

| Piece | Effort |
|---|---|
| Remaining validation (D, E) | about 1 day of work, plus a week of passive daily pulls |
| Ingest + park matching + alias table | 2–4 days |
| API + DB (answers, free windows) | 3–5 days |
| Web UI + map | 1–2 weeks |
| Hardening (alerts, ops page) | ongoing, light |

≈ **3–4 weeks part-time** for a solid MVP. That's down from 4–6, because there's no
scraper and no field-level mapping.
