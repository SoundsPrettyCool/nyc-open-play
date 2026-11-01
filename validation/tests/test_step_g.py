"""Unit tests for step G's location splitting and surface rule."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step_g_counting import occupies_soccer_surface, split_locations  # noqa: E402


def test_split_multi_location_rows():
    loc = "Randall's Island Park: East River Fields-Soccer-83 ,Randall's Island Park: Wards Meadow Fields-Soccer-74"
    assert split_locations(loc) == [
        ("Randall's Island Park", "East River Fields-Soccer-83"),
        ("Randall's Island Park", "Wards Meadow Fields-Soccer-74"),
    ]


def test_split_keeps_commas_inside_one_location():
    assert split_locations("Kennedy Playground /Raymond O'Connor: Soccer-01") == [
        ("Kennedy Playground /Raymond O'Connor", "Soccer-01")
    ]


def test_surface_rule():
    assert occupies_soccer_surface("Soccer - Non Regulation", "Softball-02")  # soccer always counts
    assert occupies_soccer_surface("Football - Youth", "Soccer-02")
    assert occupies_soccer_surface("Lacrosse", "Elston Gene Howard Field-03")
    assert not occupies_soccer_surface("Softball - Adults", "Softball-03")
    assert not occupies_soccer_surface("Baseball - Adults", "Elston Gene Howard Field-Little League-03")
    assert not occupies_soccer_surface("Tennis", "Tennis-01")
