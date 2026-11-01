"""Unit tests for parsing/normalization helpers (synthetic inputs, not real NYC data)."""

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl  # noqa: E402

from common import detect_format, normalize_label, parse_sheet, pick_column  # noqa: E402


def test_normalize_equates_common_variants():
    assert normalize_label("Ball Field #03") == normalize_label("ballfield 3")
    assert normalize_label("Soccer Field No. 2") == normalize_label("soccer 2")
    assert normalize_label("Prospect Park - Long Meadow Ballfield 07", "Prospect Park") == "long meadow ballfield 7"


def test_normalize_keeps_distinct_fields_distinct():
    assert normalize_label("Field 1") != normalize_label("Field 10")


def _xlsx(rows):
    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_xlsx_skips_title_rows_and_finds_header():
    data = _xlsx([
        ["Issued permits"],
        [],
        ["Field", "Date", "Start Time", "End Time", "Organization"],
        ["Soccer 01", "2026-11-07", "9:00 AM", "11:00 AM", "Some FC"],
        ["Field", "Date", "Start Time", "End Time", "Organization"],
        ["Soccer 02", "2026-11-07", "1:00 PM", "3:00 PM", "Other FC"],
    ])
    assert detect_format(data) == "xlsx"
    header, rows = parse_sheet(data, "xlsx")
    assert header[0] == "Field"
    assert [r["Field"] for r in rows] == ["Soccer 01", "Soccer 02"]
    assert pick_column(header, (r"^field$",)) == "Field"


def test_parse_html_table():
    html = b"""<html><body><table>
      <tr><th>Field</th><th>Date</th><th>Start</th><th>Permittee</th></tr>
      <tr><td>Soccer 1</td><td>11/07/2026</td><td>9:00</td><td>Some FC</td></tr>
    </table></body></html>"""
    assert detect_format(html) == "html"
    header, rows = parse_sheet(html, "html")
    assert rows == [{"Field": "Soccer 1", "Date": "11/07/2026", "Start": "9:00", "Permittee": "Some FC"}]


def test_parse_csv():
    data = b"Field,Date,Start Time,End Time\nSoccer 1,2026-11-07,09:00,11:00\n"
    assert detect_format(data, "text/csv") == "csv"
    _, rows = parse_sheet(data, "csv")
    assert rows[0]["End Time"] == "11:00"
