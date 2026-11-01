"""Unit tests for app/soccer.py (synthetic inputs; no network)."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from soccer import (  # noqa: E402
    ParkMatcher,
    Permit,
    field_count,
    is_soccer_field,
    occupies_soccer_surface,
    parse_permits,
    split_locations,
)

PROPS = [
    {"gispropnum": "M011", "signname": "Chelsea Park", "name311": "Chelsea Park"},
    {"gispropnum": "M144", "signname": "John V. Lindsay East River Park"},
    {"gispropnum": "M071", "signname": "Riverside Park"},
    {"gispropnum": "M072", "signname": "Riverside Park"},
    {"gispropnum": "Q099", "signname": "Flushing Meadows Corona Park"},
]
AREAS = [{"gispropnum": "M011", "propertyname": "Chelsea Pk"}]


def matcher():
    return ParkMatcher(PROPS, AREAS, prefer={"M011", "M071", "Q099"}, aliases={"East River Park": "M144"})


def event(loc, start="2026-11-08T08:00:00.000", end="2026-11-08T09:00:00.000",
          name="Soccer - Non Regulation", etype="Sport - Youth", eid="1"):
    return {"event_id": eid, "event_location": loc, "start_date_time": start, "end_date_time": end,
            "event_name": name, "event_type": etype}


def test_is_soccer_field_either_column():
    assert is_soccer_field({"regulation_soccer": True})
    assert is_soccer_field({"nonregulation_soccer": "true"})
    assert not is_soccer_field({"regulation_soccer": False, "nonregulation_soccer": False})


def test_surface_rule():
    assert occupies_soccer_surface("Soccer - Non Regulation", "Softball-02")
    assert occupies_soccer_surface("Football - Youth", "Soccer-02")
    assert not occupies_soccer_surface("Softball - Adults", "Softball-03")
    assert not occupies_soccer_surface("Baseball - Adults", "Elston Gene Howard Field-03")


def test_split_multi_location():
    assert split_locations("A Park: Soccer-01 ,A Park: Soccer-02") == [("A Park", "Soccer-01"), ("A Park", "Soccer-02")]


def test_matcher_exact_alias_secondary_and_ambiguity():
    m = matcher()
    assert m.match("Chelsea Park") == "M011"
    assert m.match("East River Park") == "M144"  # explicit alias
    assert m.match("Chelsea Pk") == "M011"  # Permit Areas name
    assert m.match("Riverside Park") == "M071"  # two IDs; prefer the one with soccer fields
    assert m.match("Nowhere Playground") is None


def test_parse_permits_matches_parks_and_flags_unclear_times():
    events = [
        event("Chelsea Park: Soccer-01"),
        event("Chelsea Park: Soccer-01", start="2026-11-08T15:00:00.000", end="2026-11-08T15:00:00.000", eid="2"),
        event("Chelsea Park: Softball-01", name="Softball - Adults", eid="3"),  # not a soccer surface
        event("Nowhere Playground: Soccer-01", eid="4"),
    ]
    permits, unmatched = parse_permits(events, matcher())
    assert [(p.park, p.event_id, p.unclear) for p in permits] == [("M011", "1", False), ("M011", "2", True)]
    assert unmatched == {"Nowhere Playground": 1}
    assert permits[0].kind == "Youth"
    assert permits[1].to_json()["unclear"] is True


def test_field_count_uses_permit_labels_when_dataset_undercounts():
    assert field_count(1, {"Football-01", "Football-02"}) == 2
    assert field_count(7, {"Soccer-01"}) == 7
    assert field_count(0, set()) == 0


def test_permit_json_shape():
    p = Permit("9", "M011", "Soccer-01", "Soccer", "Adult", datetime(2026, 11, 8, 19), datetime(2026, 11, 8, 22))
    assert p.to_json() == {"id": "9", "label": "Soccer-01", "sport": "Soccer", "kind": "Adult",
                           "start": "2026-11-08T19:00", "end": "2026-11-08T22:00", "unclear": False}
