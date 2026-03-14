"""Tests for MCP tools — all tools mocked, no real engine calls."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class FakeModel:
    name: str = "qwen3.5:35b"
    size_vram: int = 21_000_000_000
    size_total: int = 22_000_000_000
    format: str = "gguf"
    quantization: str = "Q4_K_M"
    context_length: int = 32768


@dataclass
class FakeEngine:
    name: str = "ollama"
    base_url: str = "http://localhost:11434"
    _reachable: bool = True

    def is_reachable(self) -> bool:
        return self._reachable

    def version(self) -> str:
        return "0.6.2"

    def list_running(self) -> list:
        return [FakeModel()]

    def scrape_metrics(self) -> dict:
        return {}


@dataclass
class FakeMem:
    total: int = 64 * 1024**3
    used: int = 32 * 1024**3
    pressure: str = "normal"


@dataclass
class FakeThermal:
    level: str = "nominal"
    speed_limit: int = 100


@dataclass
class FakeGpu:
    utilization_pct: float = 15.0
    renderer_pct: float = 12.0
    tiler_pct: float = 8.0
    mem_in_use: int = 4_000_000_000
    mem_allocated: int = 8_000_000_000


@dataclass
class FakeBenchRun:
    ts: int = 0
    model: str = "qwen3.5:35b"
    results: list = field(default_factory=lambda: [{"engine": "ollama", "tok_per_sec": 42.0}])
    errors: list = field(default_factory=list)


@dataclass
class FakeCheckResult:
    category: str = "system"
    name: str = "Apple Silicon"
    status: str = "ok"
    message: str = "arm64"
    fix: str = ""


@dataclass
class FakeRec:
    engine: str = "ollama"
    model: str = "qwen3.5:35b"
    score: float = 85.0
    median_tok_s: float = 42.0
    median_ttft_ms: float = 120.0
    vram_bytes: int = 21_000_000_000
    source: str = "local"
    confidence: str = "high"
    reason: str = "Best throughput"
    caveats: list = field(default_factory=list)


@pytest.fixture
def mock_ctx():
    """Create a mock MCP Context with MCPContext in lifespan_context."""
    from asiai.mcp.server import MCPContext

    engine = FakeEngine()
    mcp_ctx = MCPContext(engines=[engine], db_path=":memory:")
    ctx = MagicMock()
    ctx.request_context.lifespan_context = mcp_ctx
    return ctx


# ---------------------------------------------------------------------------
# check_inference_health
# ---------------------------------------------------------------------------


class TestCheckInferenceHealth:
    @pytest.mark.asyncio
    @patch("asiai.collectors.gpu.collect_gpu", return_value=FakeGpu())
    @patch("asiai.collectors.system.collect_thermal", return_value=FakeThermal())
    @patch("asiai.collectors.system.collect_memory", return_value=FakeMem())
    @patch("asiai.collectors.snapshot.collect_engines_status")
    async def test_healthy(self, mock_status, mock_mem, mock_thermal, mock_gpu, mock_ctx):
        mock_status.return_value = [{"name": "ollama", "reachable": True}]

        from asiai.mcp.tools import check_inference_health

        result = await check_inference_health(mock_ctx)

        assert result["status"] == "ok"
        assert result["engines"]["ollama"] is True
        assert result["memory_pressure"] == "normal"
        assert result["thermal_level"] == "nominal"
        assert result["gpu_utilization_pct"] == 15.0
        assert "ts" in result

    @pytest.mark.asyncio
    @patch("asiai.collectors.gpu.collect_gpu", return_value=FakeGpu())
    @patch("asiai.collectors.system.collect_thermal", return_value=FakeThermal())
    @patch("asiai.collectors.system.collect_memory", return_value=FakeMem())
    @patch("asiai.collectors.snapshot.collect_engines_status")
    async def test_degraded(self, mock_status, mock_mem, mock_thermal, mock_gpu, mock_ctx):
        mock_status.return_value = [
            {"name": "ollama", "reachable": True},
            {"name": "lmstudio", "reachable": False},
        ]

        from asiai.mcp.tools import check_inference_health

        result = await check_inference_health(mock_ctx)
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    @patch("asiai.collectors.gpu.collect_gpu", return_value=FakeGpu())
    @patch("asiai.collectors.system.collect_thermal", return_value=FakeThermal())
    @patch("asiai.collectors.system.collect_memory", return_value=FakeMem())
    @patch("asiai.collectors.snapshot.collect_engines_status")
    async def test_error_no_engines(self, mock_status, mock_mem, mock_thermal, mock_gpu, mock_ctx):
        mock_status.return_value = []
        mock_ctx.request_context.lifespan_context.engines = []

        from asiai.mcp.tools import check_inference_health

        result = await check_inference_health(mock_ctx)
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# get_inference_snapshot
# ---------------------------------------------------------------------------


class TestGetInferenceSnapshot:
    @pytest.mark.asyncio
    @patch("asiai.storage.db.store_engine_status")
    @patch("asiai.storage.db.store_snapshot")
    @patch("asiai.collectors.snapshot.collect_full_snapshot")
    async def test_returns_snapshot(self, mock_collect, mock_store, mock_store_es, mock_ctx):
        fake_snap = {
            "ts": 123,
            "cpu_load_1": 1.5,
            "mem_total": 64 * 1024**3,
            "engines_status": [{"name": "ollama", "reachable": True}],
        }
        mock_collect.return_value = fake_snap

        from asiai.mcp.tools import get_inference_snapshot

        result = await get_inference_snapshot(mock_ctx)

        assert result["ts"] == 123
        mock_store.assert_called_once()
        mock_store_es.assert_called_once()


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestListModels:
    @pytest.mark.asyncio
    async def test_returns_models(self, mock_ctx):
        from asiai.mcp.tools import list_models

        result = await list_models(mock_ctx)

        assert result["total_models"] == 1
        assert result["all_models"][0]["name"] == "qwen3.5:35b"
        assert result["all_models"][0]["engine"] == "ollama"

    @pytest.mark.asyncio
    async def test_unreachable_engine_skipped(self, mock_ctx):
        mock_ctx.request_context.lifespan_context.engines[0]._reachable = False

        from asiai.mcp.tools import list_models

        result = await list_models(mock_ctx)
        assert result["total_models"] == 0


# ---------------------------------------------------------------------------
# detect_engines
# ---------------------------------------------------------------------------


class TestDetectEngines:
    @pytest.mark.asyncio
    @patch("asiai.cli._discover_engines")
    async def test_detects_engines(self, mock_discover, mock_ctx):
        mock_discover.return_value = [FakeEngine()]

        from asiai.mcp.tools import detect_engines

        result = await detect_engines(mock_ctx)

        assert result["engines_found"] == 1
        assert result["engines"][0]["engine"] == "ollama"
        assert result["engines"][0]["models_loaded"] == 1


# ---------------------------------------------------------------------------
# run_benchmark
# ---------------------------------------------------------------------------


class TestRunBenchmark:
    @pytest.mark.asyncio
    @patch("asiai.storage.db.store_benchmark")
    @patch("asiai.benchmark.reporter.aggregate_results", return_value={"engines": {}})
    @patch("asiai.benchmark.runner.run_benchmark", return_value=FakeBenchRun())
    @patch("asiai.benchmark.runner.find_common_model", return_value="qwen3.5:35b")
    async def test_runs_benchmark(self, mock_find, mock_bench, mock_agg, mock_store, mock_ctx):
        from asiai.mcp.tools import run_benchmark

        result = await run_benchmark(mock_ctx, model="qwen3.5:35b")

        assert result["model"] == "qwen3.5:35b"

    @pytest.mark.asyncio
    async def test_rate_limited(self, mock_ctx):
        mock_ctx.request_context.lifespan_context.last_bench_ts = time.time()

        from asiai.mcp.tools import run_benchmark

        result = await run_benchmark(mock_ctx)
        assert "error" in result
        assert "Rate limited" in result["error"]

    @pytest.mark.asyncio
    async def test_no_engines(self, mock_ctx):
        mock_ctx.request_context.lifespan_context.engines = []

        from asiai.mcp.tools import run_benchmark

        result = await run_benchmark(mock_ctx)
        assert "error" in result
        assert "No inference engines" in result["error"]

    @pytest.mark.asyncio
    @patch("asiai.benchmark.runner.find_common_model", return_value="")
    async def test_no_model(self, mock_find, mock_ctx):
        from asiai.mcp.tools import run_benchmark

        result = await run_benchmark(mock_ctx)
        assert "error" in result
        assert "No model" in result["error"]


# ---------------------------------------------------------------------------
# get_recommendations
# ---------------------------------------------------------------------------


class TestGetRecommendations:
    @pytest.mark.asyncio
    @patch("asiai.collectors.system.collect_memory", return_value=FakeMem())
    @patch("asiai.collectors.system.collect_hw_chip", return_value="Apple M1 Max")
    @patch("asiai.advisor.recommender.recommend", return_value=[FakeRec()])
    async def test_returns_recommendations(self, mock_rec, mock_chip, mock_mem, mock_ctx):
        from asiai.mcp.tools import get_recommendations

        result = await get_recommendations(mock_ctx)

        assert result["chip"] == "Apple M1 Max"
        assert result["ram_gb"] == 64
        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["engine"] == "ollama"
        assert result["recommendations"][0]["score"] == 85.0


# ---------------------------------------------------------------------------
# diagnose
# ---------------------------------------------------------------------------


class TestDiagnose:
    @pytest.mark.asyncio
    @patch("asiai.doctor.run_checks")
    async def test_returns_diagnostics(self, mock_checks, mock_ctx):
        mock_checks.return_value = [FakeCheckResult()]

        from asiai.mcp.tools import diagnose

        result = await diagnose(mock_ctx)

        assert result["healthy"] is True
        assert result["summary"]["ok"] == 1
        assert result["checks"][0]["name"] == "Apple Silicon"

    @pytest.mark.asyncio
    @patch("asiai.doctor.run_checks")
    async def test_unhealthy(self, mock_checks, mock_ctx):
        mock_checks.return_value = [
            FakeCheckResult(status="fail", message="not arm64"),
        ]

        from asiai.mcp.tools import diagnose

        result = await diagnose(mock_ctx)
        assert result["healthy"] is False
        assert result["summary"]["fail"] == 1


# ---------------------------------------------------------------------------
# get_metrics_history
# ---------------------------------------------------------------------------


class TestGetMetricsHistory:
    @pytest.mark.asyncio
    @patch("asiai.storage.db.query_history", return_value=[])
    async def test_returns_history(self, mock_query, mock_ctx):
        from asiai.mcp.tools import get_metrics_history

        result = await get_metrics_history(mock_ctx, hours=12)

        assert result["hours"] == 12
        assert result["entries"] == 0

    @pytest.mark.asyncio
    @patch("asiai.storage.db.query_history", return_value=[])
    async def test_clamps_hours(self, mock_query, mock_ctx):
        from asiai.mcp.tools import get_metrics_history

        result = await get_metrics_history(mock_ctx, hours=999)
        assert result["hours"] == 168

    @pytest.mark.asyncio
    @patch("asiai.storage.db.query_history", return_value=[])
    async def test_clamps_hours_min(self, mock_query, mock_ctx):
        from asiai.mcp.tools import get_metrics_history

        result = await get_metrics_history(mock_ctx, hours=-5)
        assert result["hours"] == 1


# ---------------------------------------------------------------------------
# get_benchmark_history
# ---------------------------------------------------------------------------


class TestGetBenchmarkHistory:
    @pytest.mark.asyncio
    @patch("asiai.storage.db.query_benchmarks", return_value=[])
    async def test_returns_history(self, mock_query, mock_ctx):
        from asiai.mcp.tools import get_benchmark_history

        result = await get_benchmark_history(mock_ctx, hours=48, model="qwen3.5:35b")

        assert result["total_results"] == 0
        assert result["filters"]["model"] == "qwen3.5:35b"

    @pytest.mark.asyncio
    @patch("asiai.storage.db.query_benchmarks", return_value=[{"engine": "ollama"}])
    async def test_with_results(self, mock_query, mock_ctx):
        from asiai.mcp.tools import get_benchmark_history

        result = await get_benchmark_history(mock_ctx)
        assert result["total_results"] == 1


class TestCompareEngines:
    @pytest.mark.asyncio
    @patch("asiai.storage.db.query_benchmarks", return_value=[])
    async def test_no_data(self, mock_query, mock_ctx):
        from asiai.mcp.tools import compare_engines

        result = await compare_engines(mock_ctx, model="test")
        assert "error" in result

    @pytest.mark.asyncio
    @patch(
        "asiai.storage.db.query_benchmarks",
        return_value=[
            {"engine": "ollama", "model": "test:7b", "tok_per_sec": 40.0,
             "ttft_ms": 100, "vram_bytes": 4_000_000_000, "thermal_level": "nominal",
             "thermal_speed_limit": 100, "prompt_type": "code", "run_index": 0},
            {"engine": "lmstudio", "model": "test:7b", "tok_per_sec": 55.0,
             "ttft_ms": 80, "vram_bytes": 4_000_000_000, "thermal_level": "nominal",
             "thermal_speed_limit": 100, "prompt_type": "code", "run_index": 0},
        ],
    )
    async def test_comparison(self, mock_query, mock_ctx):
        from asiai.mcp.tools import compare_engines

        result = await compare_engines(mock_ctx, model="test:7b")
        assert "comparison" in result
        assert len(result["comparison"]) == 2
        assert result["comparison"][0]["engine"] == "lmstudio"  # faster
        assert "verdict" in result
        assert "lmstudio" in result["verdict"]

    @pytest.mark.asyncio
    @patch(
        "asiai.storage.db.query_benchmarks",
        return_value=[
            {"engine": "ollama", "model": "test:7b", "tok_per_sec": 40.0,
             "ttft_ms": 100, "vram_bytes": 4_000_000_000, "thermal_level": "nominal",
             "thermal_speed_limit": 100, "prompt_type": "code", "run_index": 0},
        ],
    )
    async def test_single_engine(self, mock_query, mock_ctx):
        from asiai.mcp.tools import compare_engines

        result = await compare_engines(mock_ctx, model="test:7b")
        assert "error" in result
        assert "2 engines" in result["error"]


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestMCPCli:
    def test_mcp_help(self):
        """Verify the mcp subcommand is registered."""
        from asiai.cli import main

        with pytest.raises(SystemExit) as exc:
            main(["mcp", "--help"])
        assert exc.value.code == 0

    @patch("asiai.mcp.server.serve")
    def test_mcp_command_calls_serve(self, mock_serve):
        from asiai.cli import main

        main(["mcp"])
        mock_serve.assert_called_once_with(
            transport="stdio", host="127.0.0.1", port=8900, register=False,
        )

    @patch("asiai.mcp.server.serve")
    def test_mcp_sse_transport(self, mock_serve):
        from asiai.cli import main

        main(["mcp", "--transport", "sse", "--port", "9000"])
        mock_serve.assert_called_once_with(
            transport="sse", host="127.0.0.1", port=9000, register=False,
        )

    @patch("asiai.mcp.server.serve")
    def test_mcp_register_flag(self, mock_serve):
        from asiai.cli import main

        main(["mcp", "--register"])
        mock_serve.assert_called_once_with(
            transport="stdio", host="127.0.0.1", port=8900, register=True,
        )
