# Step D — ground-truth checklist

Permit data snapshot: 2026-11-01 18:19 · window Mon Nov 2 – Sun Nov 8

**How to check** (about 10 minutes per park):
1. Open the NYC Parks **Field & Court Permit Availability Map** in your browser and find the park.
2. **Comparison day**: for each permit below, tick it if the map shows it. Then add any
   permits the map shows that are missing here.
3. **Spot checks**: does the map agree with our answer for that time?
4. Please also note the URL of the park's permit page. We need the pattern to link to it.

Mark each box `[x]` (matches) or `[!]` (doesn't), and add a note.

⚠ About 11% of permits in the feed have an end time at or before the start time
(e.g. 1pm–12pm). We can't tell the real end time, and our counts currently ignore
these permits. For each ⚠ row, write down the time the map shows.

## Chelsea Park (`M011`): N = 1 active soccer fields in dataset

### Comparison day: Sunday Nov 8 (12 permits)

| ✓ | Time | Sport | Label |
|---|---|---|---|
| [ ] | 8am–9am | Soccer - Non Regulation | Soccer-01 |
| [ ] | 11am–1pm | Soccer - Non Regulation | Soccer-01 |
| [ ] | 12pm–3pm | Soccer - Non Regulation | Soccer-01 |
| [ ] | 1pm–12pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | Soccer-01 |
| [ ] | 1pm–3pm | Soccer - Non Regulation | Soccer-01 |
| [ ] | 1pm–3pm | Soccer - Non Regulation | Soccer-01 |
| [ ] | 3pm–3pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | Soccer-01 |
| [ ] | 3pm–4pm | Soccer - Non Regulation | Soccer-01 |
| [ ] | 4pm–11am ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | Soccer-01 |
| [ ] | 5pm–6pm | Soccer -Regulation | Soccer-01 |
| [ ] | 6pm–5:30pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer -Regulation | Soccer-01 |
| [ ] | 9pm–10pm | Soccer - Non Regulation | Soccer-01 |

Permits on the map but missing here: ________

### Spot checks

| ✓ | When | Our answer | Permits we have |
|---|---|---|---|
| [ ] | Tue Nov 3 9pm | No permits on record: all 1 look open | — |
| [ ] | Wed Nov 4 2pm | No permits on record: all 1 look open | — |
| [ ] | Wed Nov 4 7pm | No permits on record: all 1 look open | — |
| [ ] | Thu Nov 5 11am | No permits on record: all 1 look open | — |
| [ ] | Thu Nov 5 9pm | Likely fully booked (1 permits, 1 fields) | Soccer-01 |
| [ ] | Fri Nov 6 9am | Likely fully booked (1 permits, 1 fields) | Soccer-01 |
| [ ] | Fri Nov 6 11am | Likely fully booked (1 permits, 1 fields) | Soccer-01 |
| [ ] | Sat Nov 7 8am | Likely fully booked (1 permits, 1 fields) | Soccer-01 |

Notes: ________

## Central Park (`M010`): N = 7 active soccer fields in dataset

### Comparison day: Saturday Nov 7 (16 permits)

| ✓ | Time | Sport | Label |
|---|---|---|---|
| [ ] | 8am–4:30pm | Soccer - Non Regulation | North Meadow-Soccer-01 |
| [ ] | 8am–4:30pm | Soccer - Non Regulation | North Meadow-Soccer-05 |
| [ ] | 9am–11am | Soccer - Non Regulation | North Meadow-Soccer-04 |
| [ ] | 9am–11:30am | Soccer - Non Regulation | North Meadow-Soccer-06 |
| [ ] | 9am–5pm | Frisbee | North Meadow-Soccer-03 |
| [ ] | 11:30am–2pm | Miscellaneous | North Meadow-Soccer-06 |
| [ ] | 12pm–12:30pm | Soccer - Non Regulation | North Meadow-Soccer-04 |
| [ ] | 1pm–12pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | North Meadow-Soccer-01 |
| [ ] | 1pm–2:30pm | Soccer - Non Regulation | North Meadow-Soccer-04 |
| [ ] | 1pm–5:30pm | Soccer - Non Regulation | North Meadow-Soccer-03 |
| [ ] | 2:30pm–4pm | Soccer - Non Regulation | North Meadow-Soccer-03 |
| [ ] | 3pm–4pm | Soccer - Non Regulation | North Meadow-Soccer-03 |
| [ ] | 3:30pm–4:30pm | Soccer - Non Regulation | North Meadow-Soccer-04 |
| [ ] | 3:30pm–5:30pm | Soccer - Non Regulation | North Meadow-Soccer-01 |
| [ ] | 5pm–5pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | North Meadow-Soccer-04 |
| [ ] | 5pm–5:30pm | Soccer - Non Regulation | North Meadow-Soccer-06 |

Permits on the map but missing here: ________

### Spot checks

| ✓ | When | Our answer | Permits we have |
|---|---|---|---|
| [ ] | Tue Nov 3 10am | No permits on record: all 7 look open | — |
| [ ] | Tue Nov 3 8pm | No permits on record: all 7 look open | — |
| [ ] | Wed Nov 4 8am | No permits on record: all 7 look open | — |
| [ ] | Wed Nov 4 8pm | No permits on record: all 7 look open | — |
| [ ] | Fri Nov 6 12pm | About 6 of 7 fields have no permit | North Meadow-Soccer-06 |
| [ ] | Fri Nov 6 2pm | About 6 of 7 fields have no permit | North Meadow-Soccer-01 |
| [ ] | Sat Nov 7 10am | About 2 of 7 fields have no permit | North Meadow-Soccer-01, North Meadow-Soccer-03, North Meadow-Soccer-04, North Meadow-Soccer-05, North Meadow-Soccer-06 |
| [ ] | Sat Nov 7 11am | About 3 of 7 fields have no permit | North Meadow-Soccer-01, North Meadow-Soccer-03, North Meadow-Soccer-05, North Meadow-Soccer-06 |

Notes: ________

## Flushing Meadows Corona Park (`Q099`): N = 9 active soccer fields in dataset

### Comparison day: Sunday Nov 8 (21 permits)

| ✓ | Time | Sport | Label |
|---|---|---|---|
| [ ] | 7am–5pm | Soccer - Non Regulation | Soccer-03 |
| [ ] | 8am–9am | Soccer - Non Regulation | Soccer-09 |
| [ ] | 8am–10am | Soccer - Non Regulation | Soccer-08 |
| [ ] | 8am–12pm | Soccer - Non Regulation | Soccer-09 |
| [ ] | 8am–4pm | Soccer - Non Regulation | Soccer-04 |
| [ ] | 8am–5pm | Soccer - Non Regulation | Soccer-05 |
| [ ] | 8am–5pm | Soccer -Regulation | Soccer-02 |
| [ ] | 8:30am–6:30pm | Soccer - Non Regulation | Soccer-07 |
| [ ] | 9:30am–3pm | Soccer -Regulation | Soccer-06 |
| [ ] | 10am–4pm | Soccer -Regulation | Soccer-01 |
| [ ] | 2pm–9am ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | Soccer-09 |
| [ ] | 2pm–2pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | Soccer-08 |
| [ ] | 3pm–5pm | Soccer -Regulation | Soccer-08 |
| [ ] | 4pm–2pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | Soccer-03 |
| [ ] | 4pm–4pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | Soccer-08 |
| [ ] | 4pm–5pm | Soccer - Non Regulation | Soccer-06 |
| [ ] | 4pm–5:30pm | Soccer - Non Regulation | Soccer-08 |
| [ ] | 5pm–11am ⚠ **end ≤ start: what time does the map show?** ____ | Soccer -Regulation | Soccer-08 |
| [ ] | 6pm–5:30pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | Soccer-03 |
| [ ] | 6pm–5:30pm ⚠ **end ≤ start: what time does the map show?** ____ | Soccer -Regulation | Soccer-09 |
| [ ] | 6pm–8pm | Soccer - Non Regulation | Soccer-09 |

Permits on the map but missing here: ________

### Spot checks

| ✓ | When | Our answer | Permits we have |
|---|---|---|---|
| [ ] | Mon Nov 2 4pm | Likely fully booked (9 permits, 9 fields) | Soccer-01, Soccer-02, Soccer-03, Soccer-04, Soccer-05, Soccer-06, Soccer-07, Soccer-08, Soccer-09 |
| [ ] | Mon Nov 2 9pm | No permits on record: all 9 look open | — |
| [ ] | Tue Nov 3 5pm | Likely fully booked (9 permits, 9 fields) | Soccer-01, Soccer-02, Soccer-03, Soccer-04, Soccer-05, Soccer-06, Soccer-07, Soccer-08, Soccer-09 |
| [ ] | Wed Nov 4 1pm | No permits on record: all 9 look open | — |
| [ ] | Wed Nov 4 4pm | Likely fully booked (9 permits, 9 fields) | Soccer-01, Soccer-02, Soccer-03, Soccer-04, Soccer-05, Soccer-06, Soccer-07, Soccer-08, Soccer-09 |
| [ ] | Fri Nov 6 9am | About 8 of 9 fields have no permit | Soccer-08 |
| [ ] | Fri Nov 6 12pm | About 8 of 9 fields have no permit | Soccer-08 |
| [ ] | Sat Nov 7 7am | About 8 of 9 fields have no permit | Soccer-08 |

Notes: ________

## Baruch Playground (`M165`): N = 1 active soccer fields in dataset

### Comparison day: Sunday Nov 8 (14 permits)

| ✓ | Time | Sport | Label |
|---|---|---|---|
| [ ] | 8am–11am | Soccer - Non Regulation | Football-01 |
| [ ] | 9:30am–3pm | Soccer - Non Regulation | Football-01 |
| [ ] | 11am–3pm | Soccer - Non Regulation | Football-02 |
| [ ] | 12pm–12pm ⚠ **end ≤ start: what time does the map show?** ____ | Football - Youth | Football-01 |
| [ ] | 12pm–2pm | Soccer - Non Regulation | Football-01 |
| [ ] | 12pm–3pm | Football - Youth | Football-02 |
| [ ] | 1pm–2pm | Miscellaneous | Football-02 |
| [ ] | 1pm–2pm | Soccer - Non Regulation | Football-01 |
| [ ] | 2pm–3pm | Football - Youth | Football-01 |
| [ ] | 2pm–4pm | Soccer - Non Regulation | Football-01 |
| [ ] | 3pm–4:30pm | Soccer | Football-01 |
| [ ] | 3pm–4:30pm | Soccer | Football-02 |
| [ ] | 4pm–5pm | Soccer - Non Regulation | Football-01 |
| [ ] | 6pm–11am ⚠ **end ≤ start: what time does the map show?** ____ | Soccer - Non Regulation | Football-02 |

Permits on the map but missing here: ________

### Spot checks

| ✓ | When | Our answer | Permits we have |
|---|---|---|---|
| [ ] | Tue Nov 3 4pm | Likely fully booked (2 permits, 1 fields) | Football-01, Football-02 |
| [ ] | Wed Nov 4 3pm | Likely fully booked (1 permits, 1 fields) | Football-02 |
| [ ] | Wed Nov 4 4pm | Likely fully booked (2 permits, 1 fields) | Football-01, Football-02 |
| [ ] | Thu Nov 5 11am | Likely fully booked (2 permits, 1 fields) | Football-01, Football-02 |
| [ ] | Thu Nov 5 9pm | No permits on record: all 1 look open | — |
| [ ] | Fri Nov 6 6pm | No permits on record: all 1 look open | — |
| [ ] | Fri Nov 6 9pm | No permits on record: all 1 look open | — |
| [ ] | Sat Nov 7 8am | No permits on record: all 1 look open | — |

Notes: ________
