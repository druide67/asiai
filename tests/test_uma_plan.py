"""UMA cohabitation planner — verdict matrix, plan route, proxy params (É3-S10)."""

from __future__ import annotations

import json

import pytest

from asiai.fleet import config as fleet_config
from asiai.fleet.plan import (
    NodeState,
    PresetCost,
    cohabitation_verdict,
)

# ---------------------------------------------------------------------------
# Verdict matrix — pure function, no I/O
# ---------------------------------------------------------------------------

# A 64 GB node, half used, calm. Costs are chosen against the 15 % / 5 %
# headroom thresholds (9.6 GB / 3.2 GB on this node).
NODE_64GB = NodeState(
    mem_total_mb=65536.0,
    mem_used_mb=32768.0,
    pressure="normal",
    thermal_level="nominal",
)


def _cost(low: float, high: float, confidence: str = "measured") -> PresetCost:
    return PresetCost(total_mb_low=low, total_mb_high=high, confidence=confidence)


class TestVerdictMatrix:
    def test_fits_with_large_headroom(self):
        # free 32 GB - 8 GB high bound = 24 GB headroom (37 %) -> fits
        v = cohabitation_verdict(_cost(7000, 8192), NODE_64GB)
        assert v.verdict == "fits"
        assert v.advisory is True
        assert v.projected_free_mb == pytest.approx(32768 - 8192, abs=1)

    def test_tight_between_5_and_15_pct(self):
        # free 32 GB - 26 GB = 6 GB headroom (9.2 %) -> tight
        v = cohabitation_verdict(_cost(24000, 26624), NODE_64GB)
        assert v.verdict == "tight"
        assert "headroom-5-15pct" in v.reasons

    def test_jetsam_risk_below_5_pct(self):
        # free 32 GB - 31 GB = 1 GB headroom (1.5 %) -> jetsam-risk
        v = cohabitation_verdict(_cost(29000, 31744), NODE_64GB)
        assert v.verdict == "jetsam-risk"
        assert "headroom-below-5pct" in v.reasons

    @pytest.mark.parametrize("pressure", ["warn", "critical"])
    def test_pressure_forces_jetsam_risk_despite_headroom(self, pressure):
        node = NodeState(mem_total_mb=65536.0, mem_used_mb=8192.0, pressure=pressure)
        v = cohabitation_verdict(_cost(1000, 2000), node)
        assert v.verdict == "jetsam-risk"
        assert f"memory-pressure-{pressure}" in v.reasons

    @pytest.mark.parametrize("level", ["serious", "critical"])
    def test_thermal_downgrades_fits(self, level):
        node = NodeState(
            mem_total_mb=65536.0, mem_used_mb=16384.0, pressure="normal", thermal_level=level
        )
        v = cohabitation_verdict(_cost(4000, 5000), node)
        assert v.verdict == "thermal-risk"
        assert f"thermal-{level}" in v.reasons

    def test_memory_risk_outranks_thermal(self):
        node = NodeState(
            mem_total_mb=65536.0,
            mem_used_mb=32768.0,
            pressure="critical",
            thermal_level="critical",
        )
        v = cohabitation_verdict(_cost(1000, 2000), node)
        assert v.verdict == "jetsam-risk"

    def test_verdict_uses_pessimistic_bound(self):
        # Low bound would fit (24 GB), high bound leaves 2 GB -> jetsam-risk
        v = cohabitation_verdict(_cost(8192, 30720), NODE_64GB)
        assert v.verdict == "jetsam-risk"
        lo, hi = v.projected_free_band
        assert lo == pytest.approx(32768 - 30720, abs=1)
        assert hi == pytest.approx(32768 - 8192, abs=1)

    # -- fail-closed unknowns -------------------------------------------

    def test_unknown_confidence_is_unknown(self):
        v = cohabitation_verdict(_cost(1000, 2000, confidence="unknown"), NODE_64GB)
        assert v.verdict == "unknown"
        assert v.projected_free_mb is None
        assert v.headroom_pct is None

    def test_missing_confidence_is_unknown(self):
        v = cohabitation_verdict(_cost(1000, 2000, confidence=""), NODE_64GB)
        assert v.verdict == "unknown"
        assert "cost-confidence-missing" in v.reasons

    def test_zero_bounds_are_unknown(self):
        v = cohabitation_verdict(_cost(0, 0), NODE_64GB)
        assert v.verdict == "unknown"
        assert "cost-bounds-missing" in v.reasons

    def test_inverted_bounds_are_unknown(self):
        v = cohabitation_verdict(_cost(9000, 4000), NODE_64GB)
        assert v.verdict == "unknown"
        assert "cost-bounds-inverted" in v.reasons

    def test_node_without_memory_total_is_unknown(self):
        v = cohabitation_verdict(_cost(1000, 2000), NodeState(mem_total_mb=0, mem_used_mb=0))
        assert v.verdict == "unknown"
        assert "node-memory-unknown" in v.reasons

    def test_unknown_never_reports_fits(self):
        # The core fail-closed property: no component may turn missing
        # data into an optimistic verdict.
        for bad in [
            _cost(1000, 2000, confidence="guessed"),
            _cost(-5, 2000),
            _cost(1000, 2000, confidence="unknown"),
        ]:
            assert cohabitation_verdict(bad, NODE_64GB).verdict == "unknown"

    @pytest.mark.parametrize(
        "low,high",
        [
            (float("nan"), 8192.0),
            (7000.0, float("nan")),
            (float("nan"), float("nan")),
            (7000.0, float("inf")),
            (float("-inf"), 8192.0),
        ],
    )
    def test_non_finite_cost_is_unknown(self, low, high):
        # NaN sails through <=/>: without an explicit isfinite guard a
        # buggy producer would get a silent "fits" (audit H1). json.loads
        # accepts NaN/Infinity tokens, so this input is reachable from a
        # real aisrv response.
        v = cohabitation_verdict(_cost(low, high), NODE_64GB)
        assert v.verdict == "unknown"
        assert "non-finite-input" in v.reasons
        assert v.projected_free_mb is None  # nothing non-finite escapes

    def test_non_finite_node_is_unknown(self):
        node = NodeState(mem_total_mb=float("nan"), mem_used_mb=1000.0)
        assert cohabitation_verdict(_cost(1000, 2000), node).verdict == "unknown"
        node = NodeState(
            mem_total_mb=65536.0,
            mem_used_mb=1000.0,
            engine_rss_mb={"llamacpp": float("inf")},
        )
        assert cohabitation_verdict(_cost(1000, 2000), node).verdict == "unknown"

    def test_pressure_unknown_caps_fits_at_tight(self):
        # Pressure is a primary jetsam signal: when the collector could
        # not read it, headroom arithmetic alone may not claim "fits"
        # (audit M1). Worse verdicts are untouched.
        node = NodeState(mem_total_mb=65536.0, mem_used_mb=32768.0)  # pressure default
        v = cohabitation_verdict(_cost(7000, 8192), node)
        assert v.verdict == "tight"
        assert "pressure-unknown" in v.reasons
        risky = NodeState(mem_total_mb=65536.0, mem_used_mb=61440.0)
        assert cohabitation_verdict(_cost(8192, 10240), risky).verdict == "jetsam-risk"

    # -- GPU wired ceiling ----------------------------------------------

    def test_gpu_wired_ceiling_caps_fits_at_tight(self):
        node = NodeState(
            mem_total_mb=131072.0,
            mem_used_mb=16384.0,
            pressure="normal",
            gpu_wired_limit_mb=8192.0,
        )
        v = cohabitation_verdict(_cost(9000, 10240), node)
        assert v.verdict == "tight"
        assert "gpu-wired-ceiling" in v.reasons

    def test_gpu_wired_ceiling_never_upgrades_jetsam(self):
        node = NodeState(
            mem_total_mb=65536.0,
            mem_used_mb=32768.0,
            pressure="critical",
            gpu_wired_limit_mb=1024.0,
        )
        v = cohabitation_verdict(_cost(2000, 3000), node)
        assert v.verdict == "jetsam-risk"

    def test_no_ceiling_when_sysctl_zero(self):
        node = NodeState(
            mem_total_mb=65536.0, mem_used_mb=16384.0, pressure="normal", gpu_wired_limit_mb=0.0
        )
        v = cohabitation_verdict(_cost(9000, 10240), node)
        assert v.verdict == "fits"
        assert "gpu-wired-ceiling" not in v.reasons

    # -- eviction credit -------------------------------------------------

    def test_replaces_engine_credits_measured_rss(self):
        node = NodeState(
            mem_total_mb=65536.0,
            mem_used_mb=61440.0,  # only 4 GB free
            pressure="normal",
            engine_rss_mb={"llamacpp": 30720.0},
        )
        # Without the credit this would be deeply negative; with 30 GB
        # freed it fits again.
        v = cohabitation_verdict(_cost(8192, 10240), node, replaces_engine="llamacpp")
        assert v.verdict == "fits"
        assert v.eviction_set == ("llamacpp",)
        assert v.projected_free_mb == pytest.approx(4096 + 30720 - 10240, abs=1)

    def test_unknown_rss_credits_nothing(self):
        node = NodeState(mem_total_mb=65536.0, mem_used_mb=61440.0)
        v = cohabitation_verdict(_cost(8192, 10240), node, replaces_engine="llamacpp")
        assert v.verdict == "jetsam-risk"
        assert v.eviction_set == ()
        assert "eviction-credit-unknown:llamacpp" in v.reasons

    def test_as_dict_shape(self):
        d = cohabitation_verdict(_cost(7000, 8192), NODE_64GB).as_dict()
        assert d["advisory"] is True
        assert d["verdict"] == "fits"
        assert isinstance(d["projected_free_band"], list)
        assert isinstance(d["eviction_set"], list)
        assert isinstance(d["reasons"], list)
        json.dumps(d)  # JSON-serializable end to end


# ---------------------------------------------------------------------------
# Web surface — /api/v1/plan + per-node proxy params
# ---------------------------------------------------------------------------

pytest.importorskip("fastapi", reason="plan route requires FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from asiai.web.app import create_app  # noqa: E402
from asiai.web.routes import fleet as fleet_routes  # noqa: E402
from asiai.web.state import AppState  # noqa: E402


@pytest.fixture
def tmp_fleet(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "asiai"
    cfg_path = cfg_dir / "fleet.json"
    monkeypatch.setattr(fleet_config, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(fleet_config, "CONFIG_PATH", str(cfg_path))
    yield cfg_path


@pytest.fixture
def client(tmp_path, tmp_fleet):
    state = AppState(engines=[], db_path=str(tmp_path / "bench.db"))
    app = create_app(state)
    fleet_routes._rate_limiter.reset()
    fleet_routes._node_read_rate_limiter.reset()
    return TestClient(app)


def _fake_memory(total_mb=65536, used_mb=32768, pressure="normal", wired=0):
    from asiai.collectors.system import MemoryInfo

    return MemoryInfo(
        total=total_mb * 1024 * 1024,
        used=used_mb * 1024 * 1024,
        pressure=pressure,
        gpu_wired_limit_mb=wired,
    )


def _fake_thermal(level="nominal"):
    from asiai.collectors.system import ThermalInfo

    return ThermalInfo(level=level, speed_limit=100)


def _mock_cost_response(low=7000.0, high=8192.0, confidence="declared"):
    body = json.dumps(
        {
            "preset": "qwen-tuned",
            "cost": {
                "total_mb_low": low,
                "total_mb_high": high,
                "confidence": confidence,
                "components": {"weights_mb": 6000},
            },
        }
    ).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestPlanRoute:
    def test_missing_preset_is_400(self, client):
        assert client.get("/api/v1/plan").status_code == 400

    @pytest.mark.parametrize("preset", ["-lead", "a b", "x" * 80, "../etc"])
    def test_invalid_preset_is_400(self, client, preset):
        resp = client.get("/api/v1/plan", params={"preset": preset})
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_preset"

    def test_invalid_engine_is_400(self, client):
        resp = client.get("/api/v1/plan", params={"preset": "ok", "engine": "BAD ENGINE"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_engine"

    def test_no_loopback_token_degrades_to_unknown(self, client):
        with patch.object(fleet_routes.loopback, "read_token", return_value=None):
            resp = client.get("/api/v1/plan", params={"preset": "qwen-tuned"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["verdict"] == "unknown"
        assert body["advisory"] is True
        assert body["note"] == "aisctl serve not available"

    def test_planner_404_names_required_aisrv(self, client):
        import io
        import urllib.error

        err = urllib.error.HTTPError(
            url="x", code=404, msg="nope", hdrs=None, fp=io.BytesIO(b"not found")
        )
        with (
            patch.object(fleet_routes.loopback, "read_token", return_value="tok"),
            patch("urllib.request.urlopen", side_effect=err),
        ):
            resp = client.get("/api/v1/plan", params={"preset": "qwen-tuned"})
        body = resp.json()
        assert body["verdict"] == "unknown"
        assert "0.11" in body["note"]

    def test_planner_404_unknown_preset_names_the_preset(self, client):
        # The planner route 404s for a typo'd preset too — the note must
        # not misdiagnose an up-to-date aisrv as "too old".
        import io
        import urllib.error

        err = urllib.error.HTTPError(
            url="x",
            code=404,
            msg="nope",
            hdrs=None,
            fp=io.BytesIO(b'{"error": "unknown_preset"}'),
        )
        with (
            patch.object(fleet_routes.loopback, "read_token", return_value="tok"),
            patch("urllib.request.urlopen", side_effect=err),
        ):
            resp = client.get("/api/v1/plan", params={"preset": "qwen-typo"})
        body = resp.json()
        assert body["verdict"] == "unknown"
        assert body["note"] == "preset not found on this node: qwen-typo"

    def test_happy_path_fits(self, client):
        with (
            patch.object(fleet_routes.loopback, "read_token", return_value="tok"),
            patch("urllib.request.urlopen", return_value=_mock_cost_response()),
            patch("asiai.collectors.system.collect_memory", return_value=_fake_memory()),
            patch("asiai.collectors.system.collect_thermal", return_value=_fake_thermal()),
        ):
            resp = client.get("/api/v1/plan", params={"preset": "qwen-tuned"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["verdict"] == "fits"
        assert body["advisory"] is True
        assert body["preset"] == "qwen-tuned"
        assert body["cost"]["confidence"] == "declared"
        assert body["node"]["mem_total_mb"] == pytest.approx(65536, abs=1)
        assert "note" not in body

    def test_replaces_engine_uses_measured_rss(self, client):
        from asiai.collectors.system import ProcessInfo

        proc = ProcessInfo(name="llamacpp", resident_bytes=30720 * 1024 * 1024)
        with (
            patch.object(fleet_routes.loopback, "read_token", return_value="tok"),
            patch("urllib.request.urlopen", return_value=_mock_cost_response(9000, 10240)),
            patch(
                "asiai.collectors.system.collect_memory",
                return_value=_fake_memory(used_mb=61440),
            ),
            patch("asiai.collectors.system.collect_thermal", return_value=_fake_thermal()),
            patch("asiai.collectors.system.find_engine_process", return_value=proc),
        ):
            resp = client.get("/api/v1/plan", params={"preset": "qwen-tuned", "engine": "llamacpp"})
        body = resp.json()
        assert body["verdict"] == "fits"
        assert body["eviction_set"] == ["llamacpp"]

    def test_nan_in_planner_body_degrades_to_unknown(self, client):
        # json.loads accepts the non-standard NaN token, and Starlette
        # serializes with allow_nan=False — without the isfinite guard
        # this exact body turned into an unhandled 500 (audit H1).
        resp_mock = MagicMock()
        resp_mock.read.return_value = (
            b'{"preset": "qwen-tuned", "cost": {"total_mb_low": 4096,'
            b' "total_mb_high": NaN, "confidence": "computed"}}'
        )
        resp_mock.__enter__ = MagicMock(return_value=resp_mock)
        resp_mock.__exit__ = MagicMock(return_value=False)
        with (
            patch.object(fleet_routes.loopback, "read_token", return_value="tok"),
            patch("urllib.request.urlopen", return_value=resp_mock),
            patch("asiai.collectors.system.collect_memory", return_value=_fake_memory()),
            patch("asiai.collectors.system.collect_thermal", return_value=_fake_thermal()),
        ):
            resp = client.get("/api/v1/plan", params={"preset": "qwen-tuned"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["verdict"] == "unknown"
        assert "non-finite-input" in body["reasons"]

    def test_malformed_planner_body_degrades_to_unknown(self, client):
        resp_mock = MagicMock()
        resp_mock.read.return_value = b'{"cost": "not-a-dict"}'
        resp_mock.__enter__ = MagicMock(return_value=resp_mock)
        resp_mock.__exit__ = MagicMock(return_value=False)
        with (
            patch.object(fleet_routes.loopback, "read_token", return_value="tok"),
            patch("urllib.request.urlopen", return_value=resp_mock),
        ):
            resp = client.get("/api/v1/plan", params={"preset": "qwen-tuned"})
        body = resp.json()
        assert body["verdict"] == "unknown"
        assert body["note"] == "malformed planner response"


class TestPlanProxyParams:
    def _add_node(self):
        fleet_config.upsert_node("m4", "http://192.0.2.10:8899")

    def test_plan_proxied_with_valid_params(self, client, tmp_fleet):
        self._add_node()
        resp_mock = MagicMock()
        resp_mock.read.return_value = b'{"verdict": "fits"}'
        resp_mock.__enter__ = MagicMock(return_value=resp_mock)
        resp_mock.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp_mock) as mock_open:
            resp = client.get("/api/v1/fleet/m4/plan?preset=qwen-tuned.v2&engine=llamacpp")
        assert resp.status_code == 200
        url = mock_open.call_args[0][0].full_url
        assert url.startswith("http://192.0.2.10:8899/api/v1/plan")
        assert "preset=qwen-tuned.v2" in url
        assert "engine=llamacpp" in url

    def test_plan_proxy_drops_invalid_values(self, client, tmp_fleet):
        self._add_node()
        resp_mock = MagicMock()
        resp_mock.read.return_value = b"{}"
        resp_mock.__enter__ = MagicMock(return_value=resp_mock)
        resp_mock.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp_mock) as mock_open:
            client.get(
                "/api/v1/fleet/m4/plan?preset=..%2F..%2Fetc&engine=UPPER%20CASE&evil=1&hours=24"
            )
        url = mock_open.call_args[0][0].full_url
        assert "preset" not in url  # fails _PRESET_RE
        assert "engine" not in url  # fails _ENGINE_RE
        assert "evil" not in url  # not whitelisted
        assert "hours" not in url  # not whitelisted for plan

    def test_digit_params_still_validated_after_refactor(self, client, tmp_fleet):
        # Regression guard for the frozenset -> pattern-map refactor: the
        # digit-only params keep rejecting non-digits.
        self._add_node()
        resp_mock = MagicMock()
        resp_mock.read.return_value = b"[]"
        resp_mock.__enter__ = MagicMock(return_value=resp_mock)
        resp_mock.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp_mock) as mock_open:
            client.get("/api/v1/fleet/m4/history?hours=24&since=abc123")
        url = mock_open.call_args[0][0].full_url
        assert "hours=24" in url
        assert "since" not in url
