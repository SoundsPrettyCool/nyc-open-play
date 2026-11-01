"""Shared helpers for the validation scripts: HTTP, paths, normalization, sheet parsing."""

from __future__ import annotations

import csv
import io
import json
import re
import time
from pathlib import Path
from typing import Iterable

import requests

OUT = Path(__file__).resolve().parent / "out"
DATASET_ID = "qnem-b8re"
SOCRATA = "https://data.cityofnewyork.us"
USER_AGENT = (
    "soccer-open-play-validation/0.1 "
    "(personal research; low-rate; https://github.com/SoundsPrettyCool/soccer-open-play)"
)


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


class Throttle:
    """Ensures at least `delay` seconds between calls to wait()."""

    def __init__(self, delay: float):
        self.delay = delay
        self._last = 0.0

    def wait(self) -> None:
        gap = time.monotonic() - self._last
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last = time.monotonic()


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for r in rows:
            for k in r:
                if k not in fieldnames:
                    fieldnames.append(k)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------- normalization

_SYNONYMS = [
    (r"\bball\s*field\b", "ballfield"),
    (r"\bsoccer\s*field\b", "soccer"),
    (r"\bfootball\s*field\b", "football"),
    (r"\bfld\b", "field"),
    (r"\bno\.?(?=\s|\d|$)", " "),
    (r"\bnumber\b", " "),
]


def normalize_label(label: str, park_name: str | None = None) -> str:
    """Canonicalize a field label so 'Ball Field #03' == 'ballfield 3'."""
    s = (label or "").lower()
    if park_name:
        # Permit labels often look like "Prospect Park - Long Meadow Ballfield 03".
        s = s.replace(park_name.lower(), " ")
    s = s.replace("#", " ").replace("&", " and ")
    for pat, rep in _SYNONYMS:
        s = re.sub(pat, rep, s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b0+(\d)", r"\1", s)  # "03" -> "3"
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------- sheet parsing

HEADER_HINTS = ("field", "facility", "date", "start", "end", "time", "permit", "organization", "permittee", "location")


def _find_header(rows: list[list[str]]) -> int | None:
    """Index of the first row that looks like a header (>=2 hint words, >=3 cells)."""
    for i, row in enumerate(rows[:50]):
        cells = [c.strip().lower() for c in row if c and c.strip()]
        hits = sum(any(h in c for h in HEADER_HINTS) for c in cells)
        if len(cells) >= 3 and hits >= 2:
            return i
    return None


def _rows_from_bytes(data: bytes, fmt: str) -> list[list[str]]:
    if fmt == "xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        out: list[list[str]] = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                out.append(["" if v is None else str(v) for v in row])
        return out
    if fmt == "csv":
        text = data.decode("utf-8-sig", errors="replace")
        return [r for r in csv.reader(io.StringIO(text))]
    if fmt == "html":
        return _rows_from_html(data.decode("utf-8", errors="replace"))
    return []


def _rows_from_html(text: str) -> list[list[str]]:
    """Very small <table> extractor (stdlib only) for permit pages rendered as HTML."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows: list[list[str]] = []
            self._row: list[str] | None = None
            self._cell: list[str] | None = None

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self._row = []
            elif tag in ("td", "th") and self._row is not None:
                self._cell = []

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self._cell is not None and self._row is not None:
                self._row.append(" ".join("".join(self._cell).split()))
                self._cell = None
            elif tag == "tr" and self._row is not None:
                if any(self._row):
                    self.rows.append(self._row)
                self._row = None

        def handle_data(self, d):
            if self._cell is not None:
                self._cell.append(d)

    p = P()
    p.feed(text)
    return p.rows


def parse_sheet(data: bytes, fmt: str) -> tuple[list[str], list[dict]]:
    """Return (header, records). Empty header means nothing table-like was found."""
    rows = _rows_from_bytes(data, fmt)
    h = _find_header(rows)
    if h is None:
        return [], []
    header = [c.strip() for c in rows[h]]
    records = []
    for row in rows[h + 1 :]:
        if not any(c.strip() for c in row):
            continue
        if [c.strip() for c in row] == header:  # repeated header on a new sheet/page
            continue
        records.append({header[i] or f"col{i}": (row[i].strip() if i < len(row) else "") for i in range(len(header))})
    return header, records


def detect_format(data: bytes, content_type: str = "") -> str:
    if data[:2] == b"PK":
        return "xlsx"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"  # legacy Excel: not parsed, reported
    if data[:5] == b"%PDF-":
        return "pdf"
    head = data[:2000].lower()
    if b"<html" in head or b"<!doctype html" in head or "html" in content_type:
        return "html"
    if "csv" in content_type or (b"," in head and b"<" not in head):
        return "csv"
    return "unknown"


def pick_column(header: Iterable[str], patterns: Iterable[str]) -> str | None:
    header = list(header)
    for pat in patterns:
        for h in header:
            if re.search(pat, h, re.I):
                return h
    return None
