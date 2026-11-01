"""Pure data logic for the app: park matching, permit parsing, per-park summaries.

Kept free of network and file I/O so it can be unit-tested; build.py does the I/O.
Rules come from the validation work in docs/VALIDATION_FINDINGS.md.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from rapidfuzz import fuzz, process

SOCCER_SURFACE = re.compile(r"soccer|football|multi[ -]?purpose|mppa|turf|futsal", re.I)
FIELD_WORD = re.compile(r"\bfield\b", re.I)
FIELD_SPORTS = re.compile(r"soccer|football|lacrosse|rugby|frisbee", re.I)
# A row can list several locations: "Park: Soccer-01 ,Park: Soccer-02".
LOCATION_SPLIT = re.compile(r"\s*[;,]\s*(?=[^,;]+:)")


def norm(s: str | None) -> str:
    s = (s or "").lower().replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def is_soccer_field(row: dict) -> bool:
    return any(str(row.get(k)).lower() == "true" for k in ("regulation_soccer", "nonregulation_soccer"))


def occupies_soccer_surface(sport: str, label: str) -> bool:
    """Soccer permits always count; other sports only on soccer-type surfaces."""
    if "soccer" in sport.lower():
        return True
    if SOCCER_SURFACE.search(label):
        return True
    return bool(FIELD_WORD.search(label) and FIELD_SPORTS.search(sport))


def split_locations(event_location: str) -> list[tuple[str, str]]:
    out = []
    for part in LOCATION_SPLIT.split(event_location or ""):
        park, _, label = part.partition(":")
        if label.strip():
            out.append((park.strip(), label.strip()))
    return out


class ParkMatcher:
    """Permit park name -> gispropnum. Official names win over Permit Areas aliases;
    explicit aliases (data/park_aliases.csv) win over everything."""

    def __init__(self, props, areas, prefer: set[str], aliases: dict[str, str] | None = None):
        self.primary, self.secondary = defaultdict(set), defaultdict(set)
        for p in props:
            for k in ("signname", "name311"):
                if p.get(k):
                    self.primary[norm(p[k])].add(p["gispropnum"])
        for a in areas:
            if a.get("propertyname") and a.get("gispropnum"):
                self.secondary[norm(a["propertyname"])].add(a["gispropnum"])
        self.aliases = {norm(k): v for k, v in (aliases or {}).items()}
        self.keys = list(self.primary)
        self.prefer = prefer

    def _lookup(self, n):
        if n in self.aliases:
            return {self.aliases[n]}
        return self.primary.get(n) or self.secondary.get(n) or set()

    def match(self, name: str) -> str | None:
        n = norm(name)
        cands = self._lookup(n)
        if not cands:
            for part in re.split(r"\s*[/(]\s*", name):  # "A / B", "Park (School)"
                cands = self._lookup(norm(part.strip(") ")))
                if cands:
                    break
        if not cands and self.keys:
            b = process.extractOne(n, self.keys, scorer=fuzz.token_set_ratio)
            cands = self.primary[b[0]] if b and b[1] >= 95 else set()
        if len(cands) > 1:
            cands = (cands & self.prefer) or cands
        return next(iter(cands)) if len(cands) == 1 else None


@dataclass
class Permit:
    event_id: str
    park: str  # gispropnum
    label: str
    sport: str
    kind: str  # "Youth" / "Adult"
    start: datetime
    end: datetime

    @property
    def unclear(self) -> bool:
        """~11% of feed permits end at or before their start (data error)."""
        return self.end <= self.start

    def to_json(self) -> dict:
        return {
            "id": self.event_id,
            "label": self.label,
            "sport": self.sport,
            "kind": self.kind,
            "start": self.start.strftime("%Y-%m-%dT%H:%M"),
            "end": self.end.strftime("%Y-%m-%dT%H:%M"),
            "unclear": self.unclear,
        }


def parse_permits(events: list[dict], matcher: ParkMatcher) -> tuple[list[Permit], dict[str, int]]:
    """Expand feed rows into per-location soccer-surface permits matched to parks.
    Returns (permits, unmatched park name -> count)."""
    permits, unmatched = [], defaultdict(int)
    for e in events:
        sport = e.get("event_name", "")
        kind = (e.get("event_type") or "").replace("Sport - ", "")
        try:
            start = datetime.fromisoformat(e["start_date_time"][:19])
            end = datetime.fromisoformat(e["end_date_time"][:19])
        except (KeyError, ValueError):
            continue
        for park_name, label in split_locations(e.get("event_location", "")):
            if not occupies_soccer_surface(sport, label):
                continue
            pid = matcher.match(park_name)
            if not pid:
                unmatched[park_name] += 1
                continue
            permits.append(Permit(e.get("event_id", ""), pid, label, sport, kind, start, end))
    return permits, dict(unmatched)


def field_count(active_fields: int, permit_labels: set[str]) -> int:
    """N for a park: the dataset undercounts some parks, and a permit proves a surface exists."""
    return max(active_fields, len(permit_labels))
