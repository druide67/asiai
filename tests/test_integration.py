"""Integration tests — require real inference engines.

Run with: pytest --integration -v
Skipped by default in CI and normal ``pytest`` runs.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestDetectIntegration:
    def test_detect_at_least_one_engine(self):
        """At least one engine should be detected on the dev machine."""
        from asiai.engines.detect import detect_engines

        found = detect_engines()
        assert len(found) >= 1, "No engines detected — is Ollama or LM Studio running?"

    def test_detect_returns_valid_tuples(self):
        from asiai.engines.detect import detect_engines

        found = detect_engines()
        for url, name, version in found:
            assert url.startswith("http")
            assert name in ("ollama", "lmstudio", "mlxlm")


class TestModelsIntegration:
    def test_list_running_models(self):
        """At least one engine should have loaded models."""
        from asiai.engines.detect import detect_engines
        from asiai.engines.lmstudio import LMStudioEngine
        from asiai.engines.mlxlm import MlxLmEngine
        from asiai.engines.ollama import OllamaEngine

        engine_map = {
            "ollama": OllamaEngine,
            "lmstudio": LMStudioEngine,
            "mlxlm": MlxLmEngine,
        }

        found = detect_engines()
        all_models = []
        for url, name, _version in found:
            cls = engine_map.get(name)
            if cls:
                engine = cls(url)
                all_models.extend(engine.list_running())

        # It's OK if no models are loaded, but the call should not fail
        assert isinstance(all_models, list)


class TestMonitorIntegration:
    def test_snapshot_store_query(self, tmp_path):
        """Collect a snapshot, store it, query it back."""
        from asiai.collectors.snapshot import collect_snapshot
        from asiai.engines.detect import detect_engines
        from asiai.engines.lmstudio import LMStudioEngine
        from asiai.engines.mlxlm import MlxLmEngine
        from asiai.engines.ollama import OllamaEngine
        from asiai.storage.db import init_db, query_history, store_snapshot

        engine_map = {
            "ollama": OllamaEngine,
            "lmstudio": LMStudioEngine,
            "mlxlm": MlxLmEngine,
        }

        found = detect_engines()
        engines = []
        for url, name, _version in found:
            cls = engine_map.get(name)
            if cls:
                engines.append(cls(url))

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        snap = collect_snapshot(engines)
        assert snap["ts"] > 0
        assert snap["cpu_load_1"] >= 0

        store_snapshot(db_path, snap)
        history = query_history(db_path, hours=1)
        assert len(history) >= 1
        assert history[0]["ts"] == snap["ts"]


class TestBenchIntegration:
    def test_bench_real_model(self):
        """Benchmark should succeed on at least one engine with a loaded model."""
        from asiai.benchmark.runner import find_common_model, run_benchmark
        from asiai.engines.detect import detect_engines
        from asiai.engines.lmstudio import LMStudioEngine
        from asiai.engines.mlxlm import MlxLmEngine
        from asiai.engines.ollama import OllamaEngine

        engine_map = {
            "ollama": OllamaEngine,
            "lmstudio": LMStudioEngine,
            "mlxlm": MlxLmEngine,
        }

        found = detect_engines()
        engines = []
        for url, name, _version in found:
            cls = engine_map.get(name)
            if cls:
                engines.append(cls(url))

        model = find_common_model(engines, "")
        if not model:
            pytest.skip("No model loaded on any engine")

        bench_run = run_benchmark(engines, model, ["code"])
        assert len(bench_run.results) >= 1
        for r in bench_run.results:
            assert r["tok_per_sec"] > 0


class TestDoctorIntegration:
    def test_run_checks_no_exception(self):
        """Doctor checks should not raise exceptions."""
        from asiai.doctor import run_checks

        checks = run_checks()
        assert len(checks) == 8
        for c in checks:
            assert c.status in ("ok", "warn", "fail")


class TestFullPipeline:
    def test_detect_bench_store_history(self, tmp_path):
        """Full pipeline: detect → bench → store → history."""
        from asiai.benchmark.runner import find_common_model, run_benchmark
        from asiai.engines.detect import detect_engines
        from asiai.engines.lmstudio import LMStudioEngine
        from asiai.engines.mlxlm import MlxLmEngine
        from asiai.engines.ollama import OllamaEngine
        from asiai.storage.db import init_db, query_benchmarks, store_benchmark

        engine_map = {
            "ollama": OllamaEngine,
            "lmstudio": LMStudioEngine,
            "mlxlm": MlxLmEngine,
        }

        # Detect
        found = detect_engines()
        assert len(found) >= 1

        engines = []
        for url, name, _version in found:
            cls = engine_map.get(name)
            if cls:
                engines.append(cls(url))

        # Find model
        model = find_common_model(engines, "")
        if not model:
            pytest.skip("No model loaded on any engine")

        # Bench
        bench_run = run_benchmark(engines, model, ["code"])
        assert len(bench_run.results) >= 1

        # Store
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        store_benchmark(db_path, bench_run.results)

        # Query
        rows = query_benchmarks(db_path, hours=1)
        assert len(rows) >= 1
        assert rows[0]["model"] == model
