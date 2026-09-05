"""Docs that describe measurements must match the code that produces them:
these checks confront the public docs with the constants and field names the
benchmark emits, so a stale sentence turns red instead of lying for a year."""

from __future__ import annotations

import re
from pathlib import Path

from asiai.benchmark.agentic import SCHEMA_VERSION as AGENTIC_SCHEMA
from asiai.collectors.ioreport import _REQUIRED_RAILS

DOCS = Path(__file__).resolve().parents[1] / "docs"


def _section(text: str, heading_prefix: str) -> str:
    """Return the body of the `### <heading_prefix>...` section (up to the next `###`/`##`)."""
    m = re.search(rf"^### {re.escape(heading_prefix)}.*?$", text, re.M)
    assert m, f"section {heading_prefix!r} missing"
    rest = text[m.end() :]
    end = re.search(r"^##", rest, re.M)
    return rest[: end.start()] if end else rest


def test_gpu_power_metric_no_longer_claims_powermetrics_as_source():
    spec = (DOCS / "metrics-spec.md").read_text()
    m6 = _section(spec, "M6.")
    assert "IOReport" in m6
    assert re.search(r"Source: `sudo powermetrics`", m6) is None
    assert "GPU" in m6  # the legacy figure must say which rail it is


def test_soc_metric_lists_every_required_rail():
    spec = (DOCS / "metrics-spec.md").read_text()
    m9 = _section(spec, "M9.")
    names = {"gpu": "GPU", "cpu": "CPU", "dram": "DRAM", "dcs": "DCS", "ane": "ANE"}
    for rail in _REQUIRED_RAILS:
        assert names[rail] in m9, f"M9 does not name required rail {rail}"


def test_energy_per_token_documents_n_minus_one_and_usage_tokens():
    spec = (DOCS / "metrics-spec.md").read_text()
    m10 = _section(spec, "M10.")
    assert "completion_tokens − 1" in m10 or "completion_tokens - 1" in m10
    assert 'tokens_source == "usage"' in m10


def test_bench_modes_names_the_live_agentic_schema_version():
    text = (DOCS / "bench-modes.md").read_text()
    assert f"SCHEMA_VERSION = {AGENTIC_SCHEMA}" in text
    stale = re.findall(r"agentic-v\d+", text)
    assert set(stale) <= {AGENTIC_SCHEMA}, f"stale agentic schema versions in bench-modes: {stale}"


def test_no_doc_or_module_presents_a_stale_agentic_schema_as_current():
    """A superseded schema may be named as legacy ("legacy agentic-v3",
    "since agentic-v4"), never presented as the current one."""
    live = int(AGENTIC_SCHEMA.rsplit("v", 1)[1])
    src = Path(__file__).resolve().parents[1] / "src" / "asiai"
    offenders = []
    for path in list(DOCS.rglob("*.md")) + list(src.rglob("*.py")):
        for line in path.read_text(errors="ignore").splitlines():
            for m in re.finditer(r"agentic-v(\d+)", line):
                if int(m.group(1)) < live and not re.search(
                    r"legacy|since|older|before|from schema.*to|→|->|v\d+\s*(→|->)", line, re.I
                ):
                    offenders.append(f"{path.relative_to(src.parent.parent)}: {line.strip()[:90]}")
    assert not offenders, offenders


def test_docs_state_the_live_metrics_version():
    """`metrics_version = N` in the docs must be the value the DB writes."""
    db_src = (Path(__file__).resolve().parents[1] / "src/asiai/storage/db.py").read_text()
    live = int(re.search(r"^\s*(\d+),\s*# metrics_version", db_src, re.M).group(1))
    offenders = []
    for path in DOCS.rglob("*.md"):
        for m in re.finditer(
            r"metrics_version\W{0,3}=\W{0,3}(\d+)", path.read_text(errors="ignore")
        ):
            if int(m.group(1)) != live:
                offenders.append(f"{path.name}: metrics_version = {m.group(1)} (live: {live})")
    assert not offenders, offenders


def test_leaderboard_legend_names_the_same_rails_as_the_code():
    legend = (DOCS / "leaderboard.md").read_text()
    for word in ("GPU", "CPU", "Neural Engine", "DRAM", "memory controllers"):
        assert word in legend
    assert "lower bound" in legend


def test_no_doc_still_says_power_comes_from_sudo_powermetrics():
    offenders = []
    for md in DOCS.glob("*.md"):
        for line in md.read_text().splitlines():
            if re.search(r"watts? \(`sudo powermetrics`\)", line):
                offenders.append(f"{md.name}: {line.strip()[:80]}")
    assert not offenders, offenders
