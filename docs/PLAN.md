# Soccer Open Play — Plan

Goal: show which NYC Parks soccer fields have **no permit** at a given date and time, so
people can go play pickup, with a link to the NYC Parks map to confirm.

> **Rewritten 2026-11-01** after finding the NYC Parks slots API (findings §7). The earlier
> design, built around the Open Data permit feed `tvpp-9vvx`, is in this file's git history.
> That feed matched the NYC Parks map in only 56–72% of Chelsea Park slots (findings §4e).

| Decision | Answer |
|---|---|
| Audience | Public, aiming to grow |
| Interface | Static web page with a map |
| Granularity | **Field-level** ("Soccer-01 at Chelsea Park is open 6–7pm") |
| Horizon | **2 weeks ahead** |
| Refresh | **Twice a day** (05:17 and 17:17 New York time). The NYC Parks map itself updates daily. |
| Coverage | All active soccer fields (~370) in all boroughs |
| Stack | Python build script + static HTML/JS on GitHub Pages; Docker for tests and CI |

## 1. Data sources

| Source | Used for |
|---|---|
| **NYC Parks slots API** `$NYC_PARKS_SLOTS_API_URL?systemId=…&startDate=…` | Per-field 30-minute availability: issued permits, permits awaiting approval, pending applications, overlapping-field blocks, permit holders. **Undocumented**, but it matches the map 100% on 252 checked slots. |
| Athletic Facilities `qnem-b8re` | Soccer fields (`regulation_soccer` or `nonregulation_soccer`), `system` ID (= API `systemId`), status, surface, lights, geometry (WGS84) |
| Parks Properties `enfh-gkve` | Park names and boundaries |

No longer used: the `tvpp-9vvx` permit feed, park-name matching, the alias table, and
field-count overrides. The API is keyed by field ID, so none of that is needed.

## 2. Architecture

```
GitHub Actions (cron, twice a day)
  └─ docker: python app/build.py --weeks 2
       ├─ Open Data (fields, parks)                     a few requests
       └─ slots API: 1 request per field per week, 1.5 s apart  ~740 requests (~20 min)
  └─ writes app/site/data/{index.json, parks/<id>.json}
  └─ deploys app/site to GitHub Pages
Browser ── static HTML/JS ── reads the JSON files (never calls NYC Parks directly)
```

- **No server and no database.** The data is a few MB of JSON, refreshed on a schedule.
- The API has **no CORS headers**, so browsers can't call it anyway, and NYC's load stays
  fixed however many people use the site.
- **Politeness and safety:**
  - honest User-Agent and a fixed delay between requests,
  - retries only on 429/5xx, and a **hard stop on 403**,
  - nothing is published if more than 20% of fields fail.

## 3. How answers are computed

Per field, per 30-minute slot (from the API):

| API slot | State | Shown as |
|---|---|---|
| Not listed | free | **Open: no permit** |
| `is_issued: true` | booked | **Permitted**: holder, type, permit #, until when |
| `is_issued: false`, holder set | awaiting | **Permit awaiting approval** (treated as unavailable, same as the map) |
| `is_issued: false`, no holder, `num_pending_permits > 0` | pending | **Open, but an application is pending** (the map shows "\*Available") |
| `permit_is_for_overlapping_field: true` | booked/awaiting | Same as above, noted "permit is for an overlapping field" |
| Field `featurestatus` ≠ Active | — | **Closed / inactive** |
| Data fetch failed, or beyond the window | — | **Unknown** |

- **Park summary:** "3 of 5 soccer fields open 6–7pm", plus free windows per field
  ("Soccer-01: open 9–10:30am, 6–7pm").
- Every page shows when the data was last refreshed, and links to the NYC Parks map.

## 4. Pages (MVP)

- **Search:** fuzzy park search (name or alias), borough filter, and an "open right now" count.
- **Park page:**
  - map with the park boundary and each soccer field colored by its state at the selected
    time (color plus label, never color alone),
  - date and time picker; per-field day timeline,
  - permit details on tap,
  - link to the NYC Parks map.
- **Basemap:** MapLibre GL JS with OpenFreeMap tiles (free, no key). Self-hosted Protomaps
  later if needed.
- **Disclaimer:** "Unofficial. Data from NYC Parks, refreshed twice a day. Fields can be
  closed or in informal use; confirm on the NYC Parks map."

**Later:**
- city-wide "open now near me" map,
- alerts when a field opens up,
- other sports (the API isn't soccer-specific),
- user reports of field conditions.

## 5. Status

| Piece | Status |
|---|---|
| Validation | Done (findings §1–§7) |
| Data build (`app/build.py`, `app/slots.py`) | Done and unit-tested |
| Docker + CI (`ci.yml`) | Done |
| Twice-daily refresh + Pages deploy (`refresh.yml`) | Written. Needs GitHub Pages enabled (Settings → Pages → Source: GitHub Actions). |
| Web pages | **To do** |
| Email to NYC Parks | Drafted in [EMAIL_NYC_PARKS.md](EMAIL_NYC_PARKS.md), to send |

## 6. Risks and open questions

1. **The API is undocumented.** It could change or block us. Mitigations:
   - the email asking permission and a preferred rate,
   - the 403 hard stop,
   - the last good deployment staying live after a failed build,
   - CI catching format changes through tests on a real response fixture.
2. **GitHub Actions is challenged.** NYC Parks' CloudFront serves GitHub-hosted runners a
   "Human Verification" page (HTTP 405). The build stops on it and never tries to get past it.
   The data jobs now run on a self-hosted Raspberry Pi runner
   ([RASPBERRY_PI.md](RASPBERRY_PI.md)), and the email asks NYC Parks whether that's acceptable.
3. **Does "awaiting approval" really mean unavailable for play?** It does on the map. Keep it.
4. **Closed fields that the data doesn't show** (maintenance, weather) are still possible.
   The disclaimer covers this; user reports could come later.
