# Prediction — Chelsea Park (M011), Mon Nov 2, 2026

Made 2026-11-01 from a fresh `tvpp-9vvx` pull, **before** checking the NYC Parks map.

Feed permits:

| Permit | Feed time | Type |
|---|---|---|
| #951042 | 8–9am | Sport - Adult, Soccer - Regulation |
| #951575 | 11am–1pm | Sport - Youth, Soccer - Non Regulation |
| #949970 | 3:30–5pm | Sport - Youth, Soccer - Non Regulation |
| #943204 | 9–10pm | Sport - Adult, Soccer - Non Regulation (VOLO; was 7–10pm on the map on Nov 8) |

Predicted open, 8am–10pm (feed only): **9–11am, 1–3:30pm, 5–9pm**

Hypotheses to test:
1. Pending permits are resolved close to the date, so the map shows few or none for tomorrow.
2. #943204 shows 7–10pm on the map, as it did on Nov 8 (a consistent wrong start in the feed).

## Result (map screenshot shared by the user on 2026-11-01, evening rows only)

| Time | Predicted | Map | |
|---|---|---|---|
| 5:30–6pm | Open | Available | ✅ |
| 6–9pm | Open | #943204 VOLO | ❌ |
| 9–10pm | Booked | #943204 VOLO | ✅ |

- Hypothesis 2 is **rejected**. #943204 is 6–10pm on the map on Nov 2, but 7–10pm on Nov 8,
  and 9–10pm in the feed on every date. The end time is right; the start is wrong by a
  varying amount, so no fixed correction is possible.
- Hypothesis 1 can't be judged: the screenshot doesn't show the morning, and no pending
  blocks were visible on Nov 2.
- Across all 7 evening columns (Nov 1–7, 5:30–10pm), the feed agrees with the map in
  **35 of 63 slots (56%)**. Every miss says "free" when the map says booked, and most
  fall in the 6–9pm window just before the feed's 9pm start for #943204.
