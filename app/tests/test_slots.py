"""Tests for app/slots.py using a trimmed real API response (Chelsea Park Soccer-01)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from slots import blocks_play, close_times, slot_state, to_intervals  # noqa: E402

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "slots_M011-SOCCER-1_2026-11-01.json").read_text())


def test_slot_state_rules():
    assert slot_state({"is_issued": True, "permit_holder": "VOLO"}) == "booked"
    assert slot_state({"is_issued": False, "permit_holder": "INDIVIDUAL"}) == "awaiting"
    assert slot_state({"is_issued": False, "permit_holder": None, "num_pending_permits": 1}) == "pending"
    assert blocks_play("booked") and blocks_play("awaiting") and not blocks_play("pending")


def test_intervals_merge_consecutive_slots_in_local_time():
    iv = to_intervals(FIXTURE["availability"])
    first = iv[0]
    # Nov 1 starts with Reato Soccer Academy, permit 954701, 8:00-9:00 (two slots merged).
    assert first == {"start": "2026-11-01T08:00", "end": "2026-11-01T09:00", "state": "booked",
                     "permit": 954701, "holder": "Reato Soccer Academy LLC", "type": "Youth",
                     "overlapping": False}
    # Intervals are ordered and non-overlapping.
    assert all(a["end"] <= b["start"] for a, b in zip(iv, iv[1:]))


def test_awaiting_and_pending_and_overlapping_are_preserved():
    iv = to_intervals(FIXTURE["availability"])
    assert any(i["state"] == "awaiting" and i["holder"] == "Pickup Soccer NYC" and i["start"] == "2026-11-04T19:00"
               for i in iv)
    assert any(i["state"] == "pending" and i["holder"] is None and i["start"] == "2026-11-07T08:00" for i in iv)
    assert any(i["overlapping"] and i["holder"] == "Big Apple Recreational Sports" for i in iv)


def test_different_permits_are_not_merged():
    av = {"1793538000": {"is_issued": True, "permit_number": 1, "permit_holder": "A"},
          "1793539800": {"is_issued": True, "permit_number": 2, "permit_holder": "B"}}
    assert [i["permit"] for i in to_intervals(av)] == [1, 2]


def test_close_times():
    assert close_times(FIXTURE)["2026-11-01"] == "22:00"
    assert close_times({"close": {"2026-11-01": "bad"}}) == {}
