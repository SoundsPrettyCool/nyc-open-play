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

The 4.3% was a first rough cut with a filter that was too broad. Step G (§4c)
replaces it.

## 4c. Counting check — step G

`python validation/step_g_counting.py`, using step F's downloaded data. For each park
and 30-minute slot, it compares `N` (active soccer fields in the dataset) with `B`
(distinct permit labels on soccer-type surfaces).

**Surface rule:**
- Soccer permits always count.
- Other sports count only if the label names soccer, football, multi-purpose, MPPA,
  turf or futsal.
- A bare "field" label counts only for field sports.

This skipped 4,468 baseball, softball, tennis and basketball entries.

| Measure | Result |
|---|---|
| Park-slots with any booking | 33,444 (149 parks) |
| **Consistent (`B ≤ N`)** | **94.1%** |
| `B > N` | 2.2% |
| `N = 0` but permits exist | 3.7% |
| Prime time (weekends 9–6, weekdays 5–9pm) | same picture: 94.5% consistent |
| Problem parks | **21**. Every one has a dataset count of 0 or 1 where permits show at most 2. |
| Multi-location permit rows | 84 rows list several fields at once (mostly Randall's Island); each field counts |
| Half-field labels | Only 1 in the whole feed (`Riverside Park: 107th/108th St-Soccer-01 E`). Not an issue. |
| Unmatched park names | Same 10 as §4b. Riverside Park now resolves, because official names are preferred over Permit Areas aliases. |

**Causes of the problem parks:**
- **No soccer fields in the dataset**, but soccer permits issued: 9 parks, e.g. Leif
  Ericson, Rainey, Frank Golden, Rockaway Beach Boardwalk.
- **Soccer fields all inactive or closed in the dataset**, but still permitted:
  Prall Playground, City Line Park.
- **Permits use more surfaces than the dataset lists**: 10 parks, e.g. Baruch
  Playground (79% of its slots), Seton Park, Alley Athletic, Hinton.

**Fix:** a per-park `N` override, set to the larger of the dataset's active count and
the distinct soccer-surface labels seen in permits. A permit proves the surface exists.
`problem_parks.csv` includes the suggested value. With that, every park-slot is
consistent. That result follows from how the override is defined, so it is not an
independent accuracy measure; step D (ground truth) is still needed for that.

**Side finding:** in slots where a park has *any* permit, the park is fully booked 58%
of the time, because many parks have only 1–2 fields. That means the free-windows view
(open time *between* permits) is likely the most useful feature.

## 4d. Permit time quality (found while preparing step D)

| Finding | Detail |
|---|---|
| **End at or before start** | **1,688 of 15,458 sports permits (11%)**, all same-day: 409 zero-length, the rest ending 1–7 hours *before* they start (e.g. Chelsea Park #938094, Nov 8, 1:00pm → 12:00pm). There's no consistent offset (it isn't an AM/PM mix-up), so the true end time can't be inferred. |
| Effect on step G | These permits covered zero slots, so they were **left out**. Bookings are therefore **undercounted**, and the real "fully booked" share is somewhat higher than 58%. |
| Repeated `event_id` | 2,707 IDs repeat, up to 30 rows each. These are **recurring permits expanded one row per date** (no identical rows, never two on the same date). Not duplicates. |
| Long permits | None over 24 hours; 1,580 run 6–24 hours (e.g. all-day 8am–11pm league days). |

**Decision needed** (informed by step D): how to treat a permit whose end ≤ start.
- Option A: assume a default length (e.g. the median 2 hours).
- Option B: block from the start time to the end of that day.
- Option C: show it as "permit time unclear" and answer "Unknown" for those slots.

The step D checklist flags each such permit (⚠) so the map's real time can be recorded.

## 4e. Ground truth — step D (in progress)

Observations are logged in [`validation/ground_truth.csv`](../validation/ground_truth.csv).

**Chelsea Park, Sun Nov 8** (map checked by the user on Nov 1):

| Time | Map | Our data | Verdict |
|---|---|---|---|
| 9–10:30am | Available | Free 9–11am | ✅ mostly. 10:30–11 is booked on the map and missing from our feed. |
| 4–5pm | Booked | Free | ❌ Caused by permit #951733 (below) |
| 6–7pm | Available | Free | ✅ |
| 7–9pm | Booked | Free | ❌ Probably ⚠ permit #952216 (feed: 6pm→5:30pm). Unconfirmed. |
| All other hours | Booked | Booked | ✅ |

- **Permit #951733 is confirmed on the map as 3–5pm**, Sport - Adult, issued to NYC Soccer
  Collective. The feed has **3pm → 3pm**. So for this permit the **start is correct and
  the end is wrong**, and the same wrong end appears on all four of its dates.
- **The permits with valid times all agree with the map.** Every wrong answer that day
  comes from ⚠ permits we ignored, or from a short booking missing from the feed. Together
  they made us show about 3 hours as open that were actually booked.
- **The map shows permittee names; the feed doesn't.**

**Implication so far:** treat a ⚠ permit as *starting* at its feed start, with an
unknown end. A slot at or after that start answers **"Unknown: permit time unclear"**
until the next valid permit or the end of the day. A guessed fixed length would have
blocked 6–7pm, which the map shows as open. This is based on one confirmed case, so
more checks are needed.

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
