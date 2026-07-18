"""Tests for the Bench page v2 — mode dispatch, validation, report endpoint."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="web routes require FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from fastapi.testclient import TestClient  # noqa: E402

from asiai.storage.db import init_db, store_bench_run  # noqa: E402
from asiai.web.app import create_app  # noqa: E402
from asiai.web.state import AppState  # noqa: E402

NOW = int(time.time())


class _FakeModel:
    name = "qwen3.5:4b"


class _FakeEngine:
    name = "llamacpp"
    base_url = "http://127.0.0.1:9999"
    api_key = ""

    def list_running(self):
        return [_FakeModel()]

    def list_available(self):
        return []

    def version(self):
        return "b9580"

    def is_reachable(self):
        return True

    def status(self):
        # Mirrors BaseEngine.status(): one aggregated pass.
        return SimpleNamespace(
            running=self.list_running(),
            available=self.list_available(),
            reachable=self.is_reachable(),
        )


@pytest.fixture
def app_state(tmp_path):
    db_path = str(tmp_path / "bench.db")
    init_db(db_path)
    return AppState(engines=[_FakeEngine()], db_path=db_path)


@pytest.fixture
def client(app_state):
    c = TestClient(create_app(app_state))
    # The CSRF middleware requires a same-origin Origin header on POSTs.
    c.headers.update({"Origin": "http://testserver"})
    return c


class TestModeDispatchValidation:
    def test_unknown_bench_type_422(self, client):
        resp = client.post("/bench/run", data={"bench_type": "evil"})
        assert resp.status_code == 422

    def test_unknown_engine_422(self, client):
        resp = client.post("/bench/run", data={"bench_type": "code", "mode_engine": "nope"})
        assert resp.status_code == 422

    def test_bad_extra_body_422(self, client):
        resp = client.post(
            "/bench/run",
            data={
                "bench_type": "code",
                "mode_engine": "llamacpp",
                "code_suites": "tool-call",
                "mode_extra_body": "not json",
            },
        )
        assert resp.status_code == 422

    def test_code_requires_a_suite(self, client):
        resp = client.post("/bench/run", data={"bench_type": "code", "mode_engine": "llamacpp"})
        assert resp.status_code == 422

    def test_unknown_language_422(self, client):
        resp = client.post(
            "/bench/run",
            data={"bench_type": "language", "mode_engine": "llamacpp", "language": "xx"},
        )
        assert resp.status_code == 422

    def test_bad_burst_sizes_422(self, client):
        resp = client.post(
            "/bench/run",
            data={"bench_type": "burst", "mode_engine": "llamacpp", "burst_sizes": "a,b"},
        )
        assert resp.status_code == 422

    def test_empty_burst_sizes_uses_cli_default(self, client, app_state):
        """An empty (untouched) burst_sizes field must fall back to the CLI
        default, not 500 — parse_burst_sizes(None) raised AttributeError."""
        from asiai.benchmark.burst import DEFAULT_BURST_SIZES

        payload = {"engine": "llamacpp", "model": "m", "started_at": NOW, "burst_results": {}}
        with patch("asiai.benchmark.burst.run_burst", return_value=payload) as m:
            resp = client.post(
                "/bench/run",
                data={"bench_type": "burst", "mode_engine": "llamacpp", "burst_sizes": ""},
            )
            assert resp.status_code == 200
            for _ in range(50):
                if app_state.get_bench_snapshot()["done"]:
                    break
                time.sleep(0.05)
        assert m.call_args.kwargs["burst_sizes"] == DEFAULT_BURST_SIZES
        assert app_state.get_bench_snapshot()["error"] == ""

    def test_running_bench_409(self, client, app_state):
        app_state.reset_bench(running=True)
        resp = client.post("/bench/run", data={"bench_type": "agentic", "mode_engine": "llamacpp"})
        assert resp.status_code == 409


class TestAuditRegressions:
    def test_instruct_default_omits_scenarios_kwarg(self, client, app_state):
        """F1: an empty selection must use the runner's OWN default set —
        passing None overrode the parameter default and crashed."""
        payload = {"engine": "llamacpp", "model": "m", "started_at": NOW, "instruct_results": {}}
        with patch("asiai.benchmark.instruct_eval.run_instruct_eval", return_value=payload) as m:
            resp = client.post(
                "/bench/run", data={"bench_type": "instruct", "mode_engine": "llamacpp"}
            )
            assert resp.status_code == 200
            for _ in range(50):
                if app_state.get_bench_snapshot()["done"]:
                    break
                time.sleep(0.05)
        assert "scenarios" not in m.call_args.kwargs
        assert app_state.get_bench_snapshot()["error"] == ""

    def test_language_all_suites_unchecked_omits_kwarg(self, client, app_state):
        """F3: same contract for language suites."""
        payload = {"engine": "llamacpp", "model": "m", "started_at": NOW, "language_results": {}}
        with patch("asiai.benchmark.language_eval.run_language_eval", return_value=payload) as m:
            resp = client.post(
                "/bench/run",
                data={"bench_type": "language", "mode_engine": "llamacpp", "language": "fr"},
            )
            assert resp.status_code == 200
            for _ in range(50):
                if app_state.get_bench_snapshot()["done"]:
                    break
                time.sleep(0.05)
        assert "suites" not in m.call_args.kwargs

    def test_judge_url_loopback_only_from_web(self, client):
        """F2: a remote judge_url would make the server POST its env API
        key to an arbitrary host (SSRF) — loopback only from the form."""
        resp = client.post(
            "/bench/run",
            data={
                "bench_type": "code",
                "mode_engine": "llamacpp",
                "code_suites": "tool-call",
                "judge_url": "http://192.0.2.7/v1",
            },
        )
        assert resp.status_code == 422
        assert "loopback" in resp.json()["error"]

    def test_judge_url_loopback_accepted(self, client, app_state):
        payload = {"engine": "llamacpp", "model": "m", "started_at": NOW, "code_results": {}}
        with patch("asiai.benchmark.code_eval.run_code_eval", return_value=payload) as m:
            resp = client.post(
                "/bench/run",
                data={
                    "bench_type": "code",
                    "mode_engine": "llamacpp",
                    "code_suites": "tool-call",
                    "judge_url": "http://127.0.0.1:8080/v1",
                },
            )
            assert resp.status_code == 200
            for _ in range(50):
                if app_state.get_bench_snapshot()["done"]:
                    break
                time.sleep(0.05)
        assert m.call_args.kwargs["judge_url"] == "http://127.0.0.1:8080/v1"

    def test_try_start_bench_is_atomic(self, app_state):
        """F4: the 409 guard is a check-and-set under the bench lock."""
        assert app_state.try_start_bench(progress="a") is True
        assert app_state.try_start_bench(progress="b") is False
        app_state.update_bench(running=False)
        assert app_state.try_start_bench(progress="c") is True


class TestModeThread:
    def test_code_mode_runs_persists_and_flags_done(self, client, app_state):
        payload = {
            "schema_version": "code-v3",
            "engine": "llamacpp",
            "model": "qwen3.5:4b",
            "started_at": NOW,
            "finished_at": NOW + 5,
            "code_results": {"tool_call": {"pct_clean": 90.0}},
        }
        with patch("asiai.benchmark.code_eval.run_code_eval", return_value=payload) as m:
            resp = client.post(
                "/bench/run",
                data={
                    "bench_type": "code",
                    "mode_engine": "llamacpp",
                    "code_suites": "tool-call",
                    "mode_runs": "2",
                },
            )
            assert resp.status_code == 200
            assert resp.json()["bench_type"] == "code"
            # The daemon thread finishes fast with a mocked runner.
            for _ in range(50):
                snap = app_state.get_bench_snapshot()
                if snap["done"]:
                    break
                time.sleep(0.05)
        snap = app_state.get_bench_snapshot()
        assert snap["done"] and not snap["running"]
        assert snap["bench_type"] == "code"
        assert snap["result_run_id"] > 0
        kwargs = m.call_args.kwargs
        assert kwargs["suites"] == ["tool-call"]
        assert kwargs["repeats"] == 2
        assert kwargs["model"] == "qwen3.5:4b"  # auto-resolved from loaded models
        # The web→runner seam forwards the engine's resolved key (None when
        # the engine has none — _FakeEngine.api_key is "").
        assert kwargs["api_key"] is None

        # The persisted run is fetchable and renders a markdown report.
        run_id = snap["result_run_id"]
        detail = client.get(f"/api/bench-runs/{run_id}")
        assert detail.status_code == 200
        report = client.get(f"/bench/report/{run_id}.md")
        assert report.status_code == 200
        assert "## Conditions" in report.text
        assert "## Provenance" in report.text

    def test_mode_thread_forwards_engine_api_key(self, client, app_state, monkeypatch):
        """A keyed engine's resolved api_key crosses the web→runner seam."""
        monkeypatch.setattr(_FakeEngine, "api_key", "sk-fake-for-seam-test")
        payload = {
            "schema_version": "code-v3",
            "engine": "llamacpp",
            "model": "qwen3.5:4b",
            "started_at": NOW,
            "finished_at": NOW + 5,
            "code_results": {},
        }
        with patch("asiai.benchmark.code_eval.run_code_eval", return_value=payload) as m:
            resp = client.post(
                "/bench/run",
                data={
                    "bench_type": "code",
                    "mode_engine": "llamacpp",
                    "code_suites": "tool-call",
                },
            )
            assert resp.status_code == 200
            for _ in range(50):
                if app_state.get_bench_snapshot()["done"]:
                    break
                time.sleep(0.05)
        assert m.call_args.kwargs["api_key"] == "sk-fake-for-seam-test"

    def test_mode_thread_error_surfaces(self, client, app_state):
        with patch(
            "asiai.benchmark.thinking_ablation.run_thinking_ablation",
            side_effect=RuntimeError("engine exploded"),
        ):
            resp = client.post(
                "/bench/run",
                data={"bench_type": "thinking-ablation", "mode_engine": "llamacpp"},
            )
            assert resp.status_code == 200
            for _ in range(50):
                snap = app_state.get_bench_snapshot()
                if snap["done"]:
                    break
                time.sleep(0.05)
        snap = app_state.get_bench_snapshot()
        assert snap["done"]
        assert "engine exploded" in snap["error"]


class TestReportEndpoint:
    def test_report_for_any_persisted_run(self, client, app_state):
        run_id = store_bench_run(
            app_state.db_path,
            {
                "ts": NOW,
                "bench_type": "agentic",
                "engine": "llamacpp",
                "model": "m",
                "score_primary": 0.9,
                "score_label": "reuse_fraction",
                "payload": json.dumps(
                    {
                        "engine": "llamacpp",
                        "model": "m",
                        "started_at": NOW,
                        "prefix_cache_reuse_verdict": "REUSED",
                        "prefix_cache_reuse": {"reuse_fraction": 0.9},
                    }
                ),
            },
        )
        resp = client.get(f"/bench/report/{run_id}.md")
        assert resp.status_code == 200
        assert "reuse_fraction" in resp.text

    def test_report_missing_404(self, client):
        assert client.get("/bench/report/424242.md").status_code == 404

    def test_report_corrupt_payload_422(self, client, app_state):
        run_id = store_bench_run(
            app_state.db_path,
            {"ts": NOW, "bench_type": "code", "engine": "e", "model": "m", "payload": "{not json"},
        )
        assert client.get(f"/bench/report/{run_id}.md").status_code == 422

    def test_card_endpoint_for_persisted_run(self, client, app_state):
        run_id = store_bench_run(
            app_state.db_path,
            {
                "ts": NOW,
                "bench_type": "agentic",
                "engine": "llamacpp",
                "model": "m",
                "payload": json.dumps(
                    {
                        "engine": "llamacpp",
                        "model": "m",
                        "started_at": NOW,
                        "prefix_cache_reuse_verdict": "REUSED",
                        "prefix_cache_reuse": {"reuse_fraction": 0.9},
                    }
                ),
            },
        )
        resp = client.get(f"/bench/card/{run_id}.svg")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/svg+xml")
        assert "REUSED" in resp.text
        assert client.get("/bench/card/424242.svg").status_code == 404

    def test_card_endpoint_corrupt_payload_422(self, client, app_state):
        run_id = store_bench_run(
            app_state.db_path,
            {"ts": NOW, "bench_type": "code", "engine": "e", "model": "m", "payload": "{nope"},
        )
        assert client.get(f"/bench/card/{run_id}.svg").status_code == 422

    def test_page_renders_type_chips(self, client):
        resp = client.get("/bench")
        assert resp.status_code == 200
        assert 'data-btype="agentic"' in resp.text
        assert 'data-btype="thinking-ablation"' in resp.text
        assert "mode-form-card" in resp.text


class _StatusAggregatingEngine:
    """Mimics the REAL producer: BaseEngine.status() aggregates
    list_running/list_available/is_reachable in one pass — the form
    reads that single status() result, never the list_* methods."""

    def is_reachable(self):
        return True

    def status(self):
        return SimpleNamespace(
            running=self.list_running(),
            available=self.list_available(),
            reachable=self.is_reachable(),
        )


class _OllamaLikeEngine(_StatusAggregatingEngine):
    """Engine with loaded models AND installed-but-not-loaded models."""

    name = "ollama"
    base_url = "http://127.0.0.1:11434"

    def list_running(self):
        return [SimpleNamespace(name="loaded:8b")]

    def list_available(self):
        # Includes the loaded model — the form data must not duplicate it.
        return [SimpleNamespace(name="loaded:8b"), SimpleNamespace(name="installed:4b")]


class _BrokenAvailableEngine(_StatusAggregatingEngine):
    """status() raises (a hung adapter breaks the whole aggregate call the
    same way) — the form must degrade to an unreachable-looking entry
    without breaking the page."""

    name = "llamacpp"
    base_url = "http://127.0.0.1:8080"

    def list_running(self):
        return [SimpleNamespace(name="m1")]

    def list_available(self):
        raise RuntimeError("engine hung")


class _UnreachableEngine(_StatusAggregatingEngine):
    name = "vllm"
    base_url = "http://127.0.0.1:8000"

    def is_reachable(self):
        return False

    def list_running(self):
        return []

    def list_available(self):
        return []


HOSTILE_NAME = 'evil"</script><script>alert(1)//'


class _HostileNameEngine(_StatusAggregatingEngine):
    """Engine whose model name tries to break out of the inline JSON block."""

    name = "llamacpp"
    base_url = "http://127.0.0.1:8080"

    def list_running(self):
        return [SimpleNamespace(name=HOSTILE_NAME)]

    def list_available(self):
        return []


class TestModeModelPicker:
    def test_page_renders_mode_model_select_with_auto(self, client):
        resp = client.get("/bench")
        assert resp.status_code == 200
        assert 'id="mode-model-select"' in resp.text
        assert 'name="mode_model"' in resp.text
        assert "(auto — first loaded model)" in resp.text
        assert 'id="mode-model-data"' in resp.text

    def test_page_renders_model_dropdown_component(self, client):
        """The visible picker is a button + menu; the select stays in the
        DOM (visually hidden) so the name= contract survives."""
        resp = client.get("/bench")
        assert resp.status_code == 200
        assert 'id="mode-model-btn"' in resp.text
        assert 'id="mode-model-menu"' in resp.text
        # The hidden select still carries the form field.
        assert 'name="mode_model" class="bn-visually-hidden"' in resp.text

    def test_page_renders_json_detail_toggle(self, client):
        """extra_body lives behind an "edit JSON detail" reveal; the field
        stays in the form (hidden inputs still submit)."""
        resp = client.get("/bench")
        assert resp.status_code == 200
        assert 'id="mode-json-toggle"' in resp.text
        assert 'name="mode_extra_body"' in resp.text

    def test_engines_for_form_has_available_key(self):
        from asiai.web.routes.bench import _get_engines_for_form

        state = SimpleNamespace(engines=[_OllamaLikeEngine()])
        (entry,) = _get_engines_for_form(state)
        assert entry["models"] == ["loaded:8b"]
        assert entry["available"] == ["installed:4b"]

    def test_available_excludes_loaded_models(self):
        from asiai.web.routes.bench import _get_engines_for_form

        state = SimpleNamespace(engines=[_OllamaLikeEngine()])
        (entry,) = _get_engines_for_form(state)
        assert "loaded:8b" not in entry["available"]

    def test_raising_adapter_degrades_without_breaking(self):
        # status() aggregates running/available/reachable in one call, so
        # a hung adapter fails the whole entry — it degrades to an
        # unreachable-looking row rather than crashing the page.
        from asiai.web.routes.bench import _get_engines_for_form

        state = SimpleNamespace(engines=[_BrokenAvailableEngine()])
        (entry,) = _get_engines_for_form(state)
        assert entry["reachable"] is False
        assert entry["models"] == []
        assert entry["available"] == []

    def test_unreachable_engine_has_empty_available(self):
        from asiai.web.routes.bench import _get_engines_for_form

        state = SimpleNamespace(engines=[_UnreachableEngine()])
        (entry,) = _get_engines_for_form(state)
        assert entry["reachable"] is False
        assert entry["models"] == []
        assert entry["available"] == []

    def test_page_still_renders_when_list_available_raises(self, tmp_path):
        db_path = str(tmp_path / "bench.db")
        init_db(db_path)
        state = AppState(engines=[_BrokenAvailableEngine()], db_path=db_path)
        resp = TestClient(create_app(state)).get("/bench")
        assert resp.status_code == 200
        assert 'id="mode-model-select"' in resp.text

    def test_hostile_model_name_cannot_break_out_of_json_script(self, tmp_path):
        """|tojson must escape < > so a model name can never close the
        <script type="application/json"> block and inject markup."""
        db_path = str(tmp_path / "bench.db")
        init_db(db_path)
        state = AppState(engines=[_HostileNameEngine()], db_path=db_path)
        resp = TestClient(create_app(state)).get("/bench")
        assert resp.status_code == 200
        # The raw closing tag from the payload must not appear anywhere.
        assert "</script><script>alert(1)" not in resp.text
        # The name survives, unicode-escaped inside the JSON block.
        assert "\\u003c/script\\u003e" in resp.text
