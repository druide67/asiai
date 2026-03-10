"""Tests for MCP resources — mocked system calls."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import patch


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
class FakeModel:
    name: str = "qwen3.5:35b"
    size_vram: int = 21_000_000_000
    format: str = "gguf"
    quantization: str = "Q4_K_M"
    context_length: int = 32768


@dataclass
class FakeEngine:
    name: str = "ollama"
    base_url: str = "http://localhost:11434"

    def is_reachable(self) -> bool:
        return True

    def version(self) -> str:
        return "0.6.2"

    def list_running(self) -> list:
        return [FakeModel()]

    def scrape_metrics(self) -> dict:
        return {}


class TestResourceStatus:
    @patch("asiai.collectors.gpu.collect_gpu", return_value=FakeGpu())
    @patch("asiai.collectors.system.collect_thermal", return_value=FakeThermal())
    @patch("asiai.collectors.system.collect_memory", return_value=FakeMem())
    def test_returns_json(self, mock_mem, mock_thermal, mock_gpu):
        from asiai.mcp.resources import resource_status

        raw = resource_status()
        data = json.loads(raw)

        assert data["memory_pressure"] == "normal"
        assert data["thermal_level"] == "nominal"
        assert data["gpu_utilization_pct"] == 15.0
        assert "ts" in data

    @patch("asiai.collectors.gpu.collect_gpu", return_value=FakeGpu())
    @patch("asiai.collectors.system.collect_thermal", return_value=FakeThermal())
    @patch("asiai.collectors.system.collect_memory", return_value=FakeMem(total=0))
    def test_zero_memory(self, mock_mem, mock_thermal, mock_gpu):
        from asiai.mcp.resources import resource_status

        data = json.loads(resource_status())
        assert data["memory_used_pct"] == 0


class TestResourceModels:
    @patch("asiai.cli._discover_engines", return_value=[FakeEngine()])
    def test_returns_models(self, mock_discover):
        from asiai.mcp.resources import resource_models

        data = json.loads(resource_models())

        assert data["total"] == 1
        assert data["models"][0]["name"] == "qwen3.5:35b"
        assert data["models"][0]["engine"] == "ollama"

    @patch("asiai.cli._discover_engines", return_value=[])
    def test_no_engines(self, mock_discover):
        from asiai.mcp.resources import resource_models

        data = json.loads(resource_models())
        assert data["total"] == 0


class TestResourceSystem:
    @patch("asiai.collectors.system.collect_uptime", return_value=86400)
    @patch("asiai.collectors.system.collect_os_version", return_value="15.3")
    @patch("asiai.collectors.system.collect_memory", return_value=FakeMem())
    @patch("asiai.collectors.system.collect_cpu_cores", return_value=10)
    @patch("asiai.collectors.system.collect_hw_chip", return_value="Apple M1 Max")
    def test_returns_system_info(self, mock_chip, mock_cores, mock_mem, mock_os, mock_uptime):
        from asiai.mcp.resources import resource_system

        data = json.loads(resource_system())

        assert data["chip"] == "Apple M1 Max"
        assert data["ram_total_gb"] == 64.0
        assert data["cpu_cores"] == 10
        assert data["os_version"] == "15.3"
        assert data["uptime_seconds"] == 86400
