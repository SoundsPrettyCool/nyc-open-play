# Validation scripts

Throwaway scripts that answer one question before any app code gets written: do the
NYC Open Data fields and the NYC Parks permit sheets line up? See
[`docs/PLAN.md`](../docs/PLAN.md) §2 for the go/no-go criteria.

Output goes to `validation/out/` (gitignored).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r validation/requirements.txt
python -m pytest -q validation/tests      # helper unit tests (synthetic data)
```

Network access needed: `data.cityofnewyork.us` and `www.nycgovparks.org`.

## Steps

### A. Open Data inventory

```bash
python validation/step_a_inventory.py
```

Downloads the dataset metadata and all rows. The script guesses the soccer marker,
park-ID column, field-name column, park-name column and geometry, and prints what it
picked. **Check those guesses against the data dictionary.** If any are wrong, re-run
without re-downloading:

```bash
python validation/step_a_inventory.py --offline --soccer-col <col> --park-col <col> --name-col <col>
```

Outputs: `out/a/columns.csv`, `soccer_fields.csv`, `soccer_parks.csv`, `summary.json`.

### F. Official permit feed join (primary path)

```bash
python validation/step_f_events.py [--offline]
```

nycgovparks.org returns a CloudFront 403 to automated clients (see
[`docs/VALIDATION_FINDINGS.md`](../docs/VALIDATION_FINDINGS.md)), so steps B/C don't
work from a server. This step pulls sports permits from NYC Open Data
**NYC Permitted Event Information** (`tvpp-9vvx`). It maps each `event_location`
(`Park: [Zone-]Sport-NN`) to a park through Parks Properties (`enfh-gkve`), and then to
a soccer field `system` ID. Writes `out/f/location_map.csv`, which seeds the manual
override table, and `out/f/summary.json`.

### G. Park-level counting check

```bash
python validation/step_g_counting.py       # uses step F's downloaded data
```

For every park and 30-minute slot, compares `N` (active soccer fields in the
dataset) with `B` (distinct permits on soccer-type surfaces), and reports the share of
slots where `B ≤ N`. Writes `out/g/problem_parks.csv`, with a suggested `N` override
per problem park, and `out/g/summary.json`.

### B. Permit inventory (blocked: kept for reference)

First open one park's issued-permits page in a browser and note the exact URL of the
page and of its spreadsheet download. Also open the Field & Court Permit
Availability Map with devtools → Network, and check for a JSON endpoint behind it.

```bash
python validation/step_b_permits.py --limit 5 --url-template 'https://www.nycgovparks.org/permits/field-and-court/issued/{park_id}'
python validation/step_b_permits.py --url-template '...'        # all parks, 3s apart
```

The script checks `robots.txt` and refuses to run if the path is disallowed. When it
gets back an HTML page, it follows the first spreadsheet/download link it finds. Each
run writes a timestamped snapshot to `out/b/snapshots/<ts>/` (raw files plus
`fetch_log.csv`).

### C. Join scoring

```bash
python validation/step_c_join.py [--label-col "<permit column>"]
```

Matches each permit field label to the park's Open Data soccer fields in three
passes: exact, then normalized ("Ball Field #03" = "ballfield 3"), then fuzzy. Writes
`out/c/matches.csv`, `unmatched.csv` and `summary.json`, and prints a verdict.

Read `unmatched.csv` before trusting the verdict. Sheets also list courts and
non-soccer ballfields, and those are expected to go unmatched. Things to look for:
- A `best_other_park` hit means the label matches a field in a *different* park,
  which points to a park-ID mismatch.
- Check whether labels for other sports name the same physical surface as a soccer
  field.
- Review fuzzy matches by hand.

### D. Ground truth (manual)

```bash
python validation/step_d_checklist.py [--parks M011,M010,Q099,M165] [--days 7]
```

Generates `out/d/checklist.md`, a copy of which is committed as
`docs/STEP_D_CHECKLIST.md`. For each park it lists one comparison day (every permit we
have, to tick off against the Availability Map) and spot-check slots with our
predicted answer. Permits with end ≤ start are flagged ⚠ so the map's real time can be
recorded. Re-run `step_f_events.py` first so the data is fresh.

Original manual plan:

- Pick 3 parks (small, medium, Prospect/Flushing-size). For ~10 date/time slots each,
  compare the parsed permits with the Availability Map.
- Spot-check ~10 field geometries: convert EPSG:2263 → 4326 and compare against
  aerial imagery. If `summary.json` says the geometry already looks like WGS84, skip
  the conversion.

### E. Churn

Run step B twice a day for about a week (cron or similar), then:

```bash
python validation/step_e_diff.py            # oldest vs newest
python validation/step_e_diff.py OLD NEW
```

This shows how often sheets change, and whether revocations show up as deleted rows
or as a status change.
