# Validation findings — 2026-11-01

**Verdict: GO, using a different permit source than planned.**
NYC Open Data publishes approved Parks sports permits through an official API.
With park-level answers (the current design), **92.4% of soccer permits map to a park
automatically**, and a 10-row alias table covers the rest (§4b). Field-level matching
(64% automatic) is kept below for reference.

Reproduce: `python validation/step_a_inventory.py && python validation/step_f_events.py`.

## 1. Athletic Facilities (`qnem-b8re`) — step A

| Finding | Detail |
|---|---|
| Rows | 6,951 facilities |
| Soccer marker | Two checkbox columns, `regulation_soccer` and `nonregulation_soccer`. Use **either**. |
| Soccer fields | **410** in **215 parks** (370 Active, 31 Inactive, 6 Closed Temporarily, 3 Removed) |
| Park ID | `gispropnum` (e.g. `B073`). Pattern: borough letter + 3 digits, sometimes a letter suffix. |
| Field ID | `system`, e.g. `B073-ZN15-SOCCER-3`, `M105-SOCCER-1`, `B008-03-FOOTBALL-1` |
| Field names | **None.** There's no park name or human-readable field name. Names come from Parks Properties. |
| Geometry | `multipolygon` for **all** rows, **already WGS84** via the API. No 2263→4326 conversion needed. |
| Status | `featurestatus` (Active / Inactive / Closed Temporarily / Removed). This partly covers "field is closed". |
| Shared use | Most soccer fields are also permittable for other sports (youth football 228, adult football 174, frisbee 144, lacrosse 102, rugby 85…). The **physical surface** matters, not the sport. |
| `primary_sport` | Codes: `SCR` 292, `MPPA` 62, `FTB` 45, … |

## 2. nycgovparks.org — step B: BLOCKED

- `robots.txt` returns 200 and doesn't disallow `/permits/`.
- Every page, **including the homepage**, returns a **CloudFront 403 "Request blocked"** to
  an honestly identified client from this cloud environment.
- We didn't try to get around it (e.g. by faking a browser user-agent). The site is
  plainly blocking automated or cloud-hosted clients.
- Untested: whether a residential IP gets through. Either way, building on a source that
  actively blocks bots is a bad foundation. **Dropped as the primary source.**

## 3. Official alternative: NYC Permitted Event Information (`tvpp-9vvx`)

The source was found while investigating step B. Step F scores the join.

| Finding | Detail |
|---|---|
| Publisher / freshness | NYC Open Data, updated **daily** (last update 2026-10-31) |
| Horizon | Approved events "within the next month": 13,448 sport permits start in the next 31 days, 58 later |
| Sports permits | 15,458 rows with `event_type` `Sport - Youth` / `Sport - Adult`, all `event_agency = Parks Department` |
| Soccer permits | **9,284** (`event_name` = `Soccer - Non Regulation` or `Soccer -Regulation`) |
| Time | `start_date_time` / `end_date_time` per booking, as local time with no time zone |
| Location | `event_location` = `Park Name: [Zone-]Sport-NN`, e.g. `Central Park: North Meadow-Soccer-03` |
| **Permittee** | **Not published.** `event_name` is just the sport (27 distinct values). |
| `cemsid` | Present, but only 12 of 15,458 appear in Parks Permit Areas (`c5vm-g2dk`). **Not a usable join key** for fields. |

## 4. Join scoring — step F

Path: `event_location` → park name → `gispropnum` (Parks Properties `enfh-gkve` +
Permit Areas names) → soccer field `system`.

| Tier | Share of soccer permits |
|---|---|
| 1. Same sport token + number as `system` | 52.9% |
| 2. Unique number among the park's soccer fields | 7.8% |
| 3. Park has exactly one active soccer field | 3.7% |
| **Auto-matched total** | **64.3%** (163 of 265 locations) |
| Ambiguous (several candidate fields) | 26.9%, mostly Randall's Island (35 labels), Flushing Meadows, Crotona |
| Park name not resolved | 7.6% (e.g. "East River Park", "Reverend T. Wendell Foster Park") |
| Park has no soccer-flagged field | 1.2% (e.g. Leif Ericson "Dust Bowl") |

- Only **265 distinct soccer permit locations** exist; the top 100 cover 71% of permits.
- 146 of 370 active soccer fields have at least one permit in the window.
- Numbering doesn't line up across sources. McCarren's `Soccer-01` is
  `B058-ZN02-FOOTBALL-1`, and `B058-ZN02-SOCCER-1` is Inactive. Robert Moses Playground's
  `Soccer-01` is `M158-HOCKEY-1`. Tier 1 can therefore be confidently wrong, so the
  override table must be **reviewed**, not just filled in.

## 4b. Park-level matching (current design)

The app now answers per park ("X of N soccer fields free"), so permits only need to
map to a **park**.

| Measure | Result |
|---|---|
| Soccer permits mapped to a park automatically | **8,579 / 9,284 (92.4%)** |
| Distinct park names that don't map | **10**: East River Park, Reverend T. Wendell Foster Park, Shore Road Park and Parkway, Kissena Corridor West, Big Bush Park, Kennedy Playground /Raymond O'Connor, Addabbo Park, Scarangella Park, Roy Wilkins Park, Parque De Los Ninos. A 10-row alias table covers them. |
| Park-hours where distinct booked labels > active soccer fields | 729 / 17,106 (**4.3%**). Worst: M165, B058 (McCarren), R106, M104 (Randall's Island). |

The 4.3% is a **first rough cut**. The filter for "on a soccer surface" was too broad
(it matched any label containing "field", including softball fields). The same broad
filter produced 11,103 park-hours that looked fully booked, a figure not to be trusted
yet. Tightening the filter and re-measuring is step G.

## 5. What this changes in the plan

> Items 4 and 5 below describe the earlier field-level design. They are superseded by
> park-level answers (§4b and [PLAN.md](PLAN.md) §3). Field-level mapping is now a
> "later" feature.

1. **Primary permit source → `tvpp-9vvx`** via the Socrata API. There's no scraping, no
   CORS problem (Socrata allows browser requests), and no undocumented endpoint.
2. **"Who holds the permit" isn't available.** Answers become "Permitted (youth
   soccer) 4–6 pm" without the organization's name.
3. **Horizon is about 1 month ahead**, not the whole season. Further-out dates answer "Unknown".
4. **Manual location map** (`location_map.csv` seeds it): 265 rows, 163 pre-filled, all
   reviewed once. New labels appear rarely, so alert on unmapped labels during ingest.
5. **Map:** the geometry is ready to use (WGS84 multipolygons), and it can also help
   resolve ambiguous labels by eye.
6. **Closures:** use `featurestatus` to show Inactive / Closed Temporarily fields as closed.

## 6. Still open

- Does `tvpp-9vvx` drop revoked permits promptly? Run it daily for a week and diff (step E, pointed at this source).
- Are times local (America/New_York)? Very likely. Confirm with one known permit.
- Are non-soccer permits on shared surfaces (football, lacrosse on the same turf) a
  blocker for soccer? Assume yes, and include all sports when computing a field's bookings.
- Ground truth (step D): compare one park's week with the Availability Map viewed in a browser.
