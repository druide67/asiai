"""The nine leaderboard pages must stay structurally identical.

The client script (docs/assets/js/leaderboard.js) is shared by every locale
and addresses columns by `data-col`. A page that drifts — a column added in
English only, a stale colspan, a missing view button — renders cells under
the wrong header in that locale, silently. Labels may differ; structure may not.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs"
PAGES = sorted(DOCS.glob("leaderboard*.md"))
REFERENCE = DOCS / "leaderboard.md"

EXPECTED_COLS = [
    "engine",
    "model",
    "median_tok_s",
    "median_ttft_ms",
    "median_power_watts",
    "median_tok_s_per_watt",
    "median_soc_watts",
    "median_energy_per_token_j",
    "median_energy_per_token_active_j",
    "median_idle_soc_watts",
    "last_submitted_at",
    "samples",
]
ENERGY_COLS = {
    "median_soc_watts",
    "median_energy_per_token_j",
    "median_energy_per_token_active_j",
    "median_idle_soc_watts",
}


def _cols(text: str) -> list[str]:
    return re.findall(r'data-col="([a-z_]+)"', text)


def _th_count(text: str) -> int:
    return len(re.findall(r"<th\b", text))


def test_nine_locales_present():
    assert len(PAGES) == 9, [p.name for p in PAGES]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_sortable_columns_match_reference(page: Path):
    assert _cols(page.read_text()) == EXPECTED_COLS


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_energy_columns_are_view_scoped(page: Path):
    text = page.read_text()
    for col in ENERGY_COLS:
        th = re.search(rf'<th class="([^"]*)" data-col="{col}"', text)
        assert th, f"{page.name}: {col} header missing"
        assert "lb-col-energy" in th.group(1), f"{page.name}: {col} not view-scoped"
    # Legacy GPU headers are never energy-scoped and always say GPU.
    for col in ("median_power_watts", "median_tok_s_per_watt"):
        th = re.search(rf'<th class="([^"]*)" data-col="{col}">([^<]*)</th>', text)
        assert th and "lb-col-energy" not in th.group(1)
        assert "GPU" in th.group(2), f"{page.name}: {col} label must name the GPU rail"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_colspan_and_header_count_match_reference(page: Path):
    ref = REFERENCE.read_text()
    text = page.read_text()
    assert _th_count(text) == _th_count(ref)
    ref_span = re.search(r'colspan="(\d+)"', ref).group(1)
    assert re.search(r'colspan="(\d+)"', text).group(1) == ref_span
    assert int(ref_span) == _th_count(ref)


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_view_toggle_and_labels_present(page: Path):
    text = page.read_text()
    assert text.count('class="lb-view-btn') == 2
    assert 'data-view="speed"' in text and 'data-view="energy"' in text
    assert "data-label-provenance=" in text
    # The provenance label carries both placeholders the script substitutes.
    prov = re.search(r'data-label-provenance="([^"]*)"', text).group(1)
    assert "{n}" in prov and "{b}" in prov


def test_english_page_carries_the_energy_legend():
    text = REFERENCE.read_text()
    assert 'class="lb-legend"' in text
    assert "lower bound" in text
    assert "never a zero" in text
