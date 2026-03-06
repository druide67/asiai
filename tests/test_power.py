"""Tests for power monitoring module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from asiai.collectors.power import PowerMonitor, PowerSample


class TestPowerSample:
    def test_defaults(self):
        s = PowerSample()
        assert s.gpu_watts == 0.0
        assert s.cpu_watts == 0.0
        assert s.source == ""


class TestPowerMonitor:
    def test_start_no_sudo(self):
        """Without sudo access, start() returns False."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("asiai.collectors.power.subprocess.run", return_value=mock_result):
            monitor = PowerMonitor()
            assert not monitor.start()

    def test_start_sudo_exception(self):
        """If sudo check throws, start() returns False."""
        with patch(
            "asiai.collectors.power.subprocess.run",
            side_effect=OSError("no sudo"),
        ):
            monitor = PowerMonitor()
            assert not monitor.start()

    def test_stop_no_samples(self):
        """Stop without starting returns empty sample."""
        monitor = PowerMonitor()
        sample = monitor.stop()
        assert sample.gpu_watts == 0.0
        assert "no samples" in sample.source

    def test_stop_with_samples(self):
        """Manually inject samples and verify averaging."""
        monitor = PowerMonitor()
        monitor._samples = [
            {"gpu": 15.0, "cpu": 5.0},
            {"gpu": 17.0, "cpu": 6.0},
            {"gpu": 16.0, "cpu": 5.5},
        ]
        sample = monitor.stop()
        assert sample.gpu_watts == 16.0
        assert sample.cpu_watts == 5.5
        assert "3 samples" in sample.source

    def test_stop_partial_samples(self):
        """Samples with missing keys should be handled."""
        monitor = PowerMonitor()
        monitor._samples = [
            {"gpu": 10.0},
            {"cpu": 5.0},
            {"gpu": 12.0, "cpu": 6.0},
        ]
        sample = monitor.stop()
        assert sample.gpu_watts == 11.0  # avg(10, 12)
        assert sample.cpu_watts == 5.5  # avg(5, 6)

    def test_reader_parses_mw(self):
        """Reader thread should parse mW format."""
        monitor = PowerMonitor()
        monitor._running = True
        monitor._samples = []

        # Simulate powermetrics output lines
        lines = [
            "GPU Power: 15000 mW\n",
            "CPU Power: 5000 mW\n",
            "***** Separator *****\n",
            "GPU Power: 17000 mW\n",
            "CPU Power: 6000 mW\n",
        ]

        mock_process = MagicMock()
        mock_process.stdout = iter(lines)
        monitor._process = mock_process

        # Run the reader (it will stop when lines are exhausted)
        monitor._reader()

        # Should have captured 1 complete sample (at separator) + 1 partial
        assert len(monitor._samples) >= 1
        assert monitor._samples[0]["gpu"] == 15.0  # 15000 mW -> 15 W
        assert monitor._samples[0]["cpu"] == 5.0

    def test_reader_parses_watts(self):
        """Reader thread should parse W format (no mW)."""
        monitor = PowerMonitor()
        monitor._running = True
        monitor._samples = []

        lines = [
            "GPU Power: 18.5 W\n",
            "CPU Power: 7.2 W\n",
            "***** Separator *****\n",
        ]

        mock_process = MagicMock()
        mock_process.stdout = iter(lines)
        monitor._process = mock_process

        monitor._reader()

        assert len(monitor._samples) >= 1
        assert monitor._samples[0]["gpu"] == 18.5
        assert monitor._samples[0]["cpu"] == 7.2
