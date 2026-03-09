"""Tests for the recommendation engine."""

from __future__ import annotations

from unittest.mock import patch

from asiai.advisor.recommender import (
    Recommendation,
    _compute_stability_score,
    _from_heuristics,
    _median,
    _normalize,
    recommend,
)

# ---------------------------------------------------------------------------
# Recommendation dataclass
# ---------------------------------------------------------------------------


def test_recommendation_defaults():
    """Default field values are correct."""
    rec = Recommendation(engine="ollama", model="qwen:7b", score=80.0)
    assert rec.engine == "ollama"
    assert rec.model == "qwen:7b"
    assert rec.score == 80.0
    assert rec.median_tok_s == 0.0
    assert rec.median_ttft_ms == 0.0
    assert rec.vram_bytes == 0
    assert rec.source == ""
    assert rec.confidence == ""
    assert rec.reason == ""
    assert rec.caveats == []


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


def test_normalize_basic():
    """Min-max normalization maps [10, 20, 30] to [0, 50, 100]."""
    result = _normalize([10, 20, 30])
    assert result == [0.0, 50.0, 100.0]


def test_normalize_empty():
    """Empty list returns empty list."""
    assert _normalize([]) == []


def test_normalize_all_same():
    """When all values are equal, each maps to 50."""
    result = _normalize([5, 5, 5])
    assert result == [50.0, 50.0, 50.0]


# ---------------------------------------------------------------------------
# _compute_stability_score
# ---------------------------------------------------------------------------


def test_stability_single_value():
    """A single run returns the neutral score of 70."""
    assert _compute_stability_score([42.0]) == 70.0


def test_stability_stable():
    """CV < 5% yields a score of 100."""
    # mean=100, stdev~1 => CV=0.01 < 0.05
    values = [99.0, 100.0, 101.0, 100.0, 100.0]
    assert _compute_stability_score(values) == 100.0


def test_stability_variable():
    """CV between 5% and 10% yields a score of 70."""
    # Build values with CV ~7%: mean=100, stdev~7
    values = [93.0, 100.0, 107.0, 100.0]
    import statistics

    cv = statistics.stdev(values) / statistics.mean(values)
    assert 0.05 <= cv < 0.10, f"CV {cv:.3f} not in [0.05, 0.10)"
    assert _compute_stability_score(values) == 70.0


def test_stability_unstable():
    """CV >= 10% yields a score of 40."""
    # mean~50, stdev~20 => CV~0.4
    values = [30.0, 50.0, 70.0, 50.0]
    import statistics

    cv = statistics.stdev(values) / statistics.mean(values)
    assert cv >= 0.10, f"CV {cv:.3f} not >= 0.10"
    assert _compute_stability_score(values) == 40.0


# ---------------------------------------------------------------------------
# _median
# ---------------------------------------------------------------------------


def test_median():
    """Basic median computation."""
    assert _median([1.0, 3.0, 2.0]) == 2.0
    assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5


# ---------------------------------------------------------------------------
# _from_heuristics
# ---------------------------------------------------------------------------


def test_heuristics_small_ram():
    """With 16 GB RAM only 7B-class models are recommended."""
    recs = _from_heuristics(chip="Apple M1", ram_gb=16, use_case="throughput", model_filter="")
    models_params = {r.model for r in recs}
    # All recommended models should be <= 7B (i.e. names in our heuristic list)
    for r in recs:
        assert r.source == "heuristic"
        assert r.confidence == "low"
    # Only qwen3.5:7b is <= 7B in the heuristic table
    assert "qwen3.5:7b" in models_params
    # No large models should appear
    large_models = {"qwen3.5:14b", "gemma-3:27b", "qwen3.5:35b-a3b", "llama3.1:70b"}
    assert models_params.isdisjoint(large_models)


def test_heuristics_large_ram():
    """With 64 GB RAM models up to 35B are recommended."""
    recs = _from_heuristics(chip="Apple M4 Pro", ram_gb=64, use_case="throughput", model_filter="")
    models_params = {r.model for r in recs}
    # 35B model should be included
    assert "qwen3.5:35b-a3b" in models_params
    # 70B should NOT be included
    assert "llama3.1:70b" not in models_params


def test_heuristics_model_filter():
    """Model filter narrows results to matching models only."""
    recs = _from_heuristics(
        chip="Apple M4 Pro",
        ram_gb=64,
        use_case="throughput",
        model_filter="gemma",
    )
    for r in recs:
        assert "gemma" in r.model.lower()


# ---------------------------------------------------------------------------
# recommend — integration
# ---------------------------------------------------------------------------

_MOCK_ROWS = [
    {
        "engine": "ollama",
        "model": "qwen:7b",
        "tok_per_sec": 42.0,
        "ttft_ms": 85.0,
        "vram_bytes": 7_000_000_000,
        "run_index": 0,
        "prompt_type": "short",
    },
    {
        "engine": "ollama",
        "model": "qwen:7b",
        "tok_per_sec": 43.0,
        "ttft_ms": 87.0,
        "vram_bytes": 7_000_000_000,
        "run_index": 1,
        "prompt_type": "short",
    },
    {
        "engine": "lmstudio",
        "model": "qwen:7b",
        "tok_per_sec": 38.0,
        "ttft_ms": 95.0,
        "vram_bytes": 6_500_000_000,
        "run_index": 0,
        "prompt_type": "short",
    },
]


def test_recommend_local_only():
    """recommend() uses local data when db_path is provided."""
    with patch("asiai.storage.db.query_benchmarks", return_value=_MOCK_ROWS):
        recs = recommend(
            chip="Apple M4 Pro",
            ram_gb=64,
            db_path="/tmp/fake.db",
        )
    assert len(recs) >= 1
    for r in recs:
        assert r.source == "local"
        assert r.score >= 0


def test_recommend_heuristic_fallback():
    """Without db_path, recommend() falls back to heuristics."""
    recs = recommend(chip="Apple M1 Max", ram_gb=64)
    assert len(recs) > 0
    for r in recs:
        assert r.source == "heuristic"
        assert r.confidence == "low"


def test_recommend_sorted_by_score():
    """Results are sorted by score in descending order."""
    with patch("asiai.storage.db.query_benchmarks", return_value=_MOCK_ROWS):
        recs = recommend(
            chip="Apple M4 Pro",
            ram_gb=64,
            db_path="/tmp/fake.db",
        )
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)
