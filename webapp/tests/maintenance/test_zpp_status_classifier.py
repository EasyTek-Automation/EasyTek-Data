"""Testes IM-08 — `_classify_status` do zpp_timeline_loader.

Cobre BR-14 + BR-04: mapping código SAP → categoria visual.
"""

import pytest

from src.utils.zpp_timeline_loader import _classify_status, EVOCON_PALETTE_TIMELINE


@pytest.mark.parametrize("code,expected", [
    # Breakdown codes (BR-04) → avaria
    ("201",  "avaria"),
    ("S201", "avaria"),
    ("202",  "avaria"),
    ("S202", "avaria"),
    ("203",  "avaria"),
    ("S203", "avaria"),
    ("204",  "avaria"),
    ("S204", "avaria"),
    ("205",  "avaria"),
    ("S205", "avaria"),

    # 110/S110 → mtto_auto (também breakdown code, mas categoria distinta)
    ("110",  "mtto_auto"),
    ("S110", "mtto_auto"),

    # 1XX não-breakdown → refeicao
    ("102N", "refeicao"),
    ("105",  "refeicao"),

    # Famílias por dígito principal
    ("301",  "setup"),
    ("302",  "setup"),
    ("303",  "setup"),
    ("404",  "logistica"),
    ("408",  "logistica"),
    ("417",  "logistica"),
    ("504",  "microparada"),
    ("601",  "processo"),

    # Edge cases
    (None,   "outros"),
    ("",     "outros"),
    ("   ",  "outros"),
    ("999",  "outros"),
    ("ABC",  "outros"),
    ("S",    "outros"),
])
def test_classify_status(code, expected):
    assert _classify_status(code) == expected


def test_all_statuses_have_palette_color():
    """Todo status retornado por _classify_status deve ter cor na paleta."""
    sample_codes = [
        "201", "110", "102N", "301", "404", "504", "601", None, "999",
    ]
    for code in sample_codes:
        status = _classify_status(code)
        assert status in EVOCON_PALETTE_TIMELINE, (
            f"status '{status}' (de code='{code}') não tem cor em EVOCON_PALETTE_TIMELINE"
        )
