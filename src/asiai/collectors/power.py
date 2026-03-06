"""GPU power monitoring via powermetrics (macOS).

Measures GPU power consumption during inference for tok/s per watt calculation.
Requires sudo access (uses ``sudo -n powermetrics``).
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger("asiai.collectors.power")


@dataclass
class PowerSample:
    """Aggregated power measurement."""

    gpu_watts: float = 0.0
    cpu_watts: float = 0.0
    source: str = ""


class PowerMonitor:
    """Background power monitoring using ``sudo powermetrics``.

    Usage::

        monitor = PowerMonitor()
        if monitor.start():
            # ... run inference ...
            sample = monitor.stop()
            print(f"GPU power: {sample.gpu_watts}W")
        else:
            print("No sudo access, skipping power measurement")

    Can also be used as a context manager::

        with PowerMonitor() as monitor:
            if monitor.started:
                # ... run inference ...
                pass
        sample = monitor.result
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._samples: list[dict[str, float]] = []
        self._thread: threading.Thread | None = None
        self._running = False
        self.started = False
        self.result: PowerSample = PowerSample()

    def __enter__(self) -> PowerMonitor:
        self.started = self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.started:
            self.result = self.stop()

    def start(self) -> bool:
        """Start powermetrics in background. Returns False if no sudo access."""
        # Check non-interactive sudo access for powermetrics
        try:
            result = subprocess.run(
                [
                    "sudo",
                    "-n",
                    "/usr/bin/powermetrics",
                    "--samplers",
                    "gpu_power",
                    "-n",
                    "1",
                    "-i",
                    "1",
                ],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.info("No passwordless sudo access for powermetrics")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug("sudo powermetrics check failed: %s", e)
            return False

        try:
            self._process = subprocess.Popen(
                [
                    "sudo",
                    "-n",
                    "powermetrics",
                    "--samplers",
                    "gpu_power,cpu_power",
                    "-i",
                    "500",  # 500ms sample interval
                    "--format",
                    "text",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except (FileNotFoundError, OSError) as e:
            logger.warning("Failed to start powermetrics: %s", e)
            return False

        # Validate subprocess actually started
        if self._process.poll() is not None:
            logger.warning(
                "powermetrics exited immediately with code %d", self._process.returncode
            )
            self._process = None
            return False

        self._running = True
        self._samples = []
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        # Brief pause to collect at least one sample
        time.sleep(0.6)
        return True

    def stop(self) -> PowerSample:
        """Stop monitoring and return averaged power sample."""
        self._running = False

        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.debug("powermetrics did not terminate, killing")
                try:
                    self._process.kill()
                    self._process.wait(timeout=3)
                except OSError as e:
                    logger.debug("powermetrics kill failed: %s", e)
            except OSError as e:
                logger.debug("powermetrics terminate failed: %s", e)
            self._process = None

        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

        if not self._samples:
            return PowerSample(source="powermetrics (no samples)")

        gpu_values = [s.get("gpu", 0.0) for s in self._samples if s.get("gpu", 0.0) > 0]
        cpu_values = [s.get("cpu", 0.0) for s in self._samples if s.get("cpu", 0.0) > 0]

        return PowerSample(
            gpu_watts=round(sum(gpu_values) / len(gpu_values), 2) if gpu_values else 0.0,
            cpu_watts=round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else 0.0,
            source=f"powermetrics ({len(self._samples)} samples)",
        )

    def _reader(self) -> None:
        """Read powermetrics output in background thread."""
        if not self._process or not self._process.stdout:
            return

        current: dict[str, float] = {}
        for line in self._process.stdout:
            if not self._running:
                break
            line = line.strip()

            # GPU power: pattern varies by macOS version
            # "GPU Power: 12.34 mW" or "GPU HW active residency:" section
            gpu_match = re.search(r"GPU\s+Power:\s+([\d.]+)\s*mW", line)
            if gpu_match:
                current["gpu"] = float(gpu_match.group(1)) / 1000  # mW -> W

            # Alternative: "GPU Power" in watts
            gpu_w_match = re.search(r"GPU\s+Power:\s+([\d.]+)\s*W", line)
            if gpu_w_match and "mW" not in line:
                current["gpu"] = float(gpu_w_match.group(1))

            # CPU power
            cpu_match = re.search(r"CPU\s+Power:\s+([\d.]+)\s*mW", line)
            if cpu_match:
                current["cpu"] = float(cpu_match.group(1)) / 1000

            cpu_w_match = re.search(r"CPU\s+Power:\s+([\d.]+)\s*W", line)
            if cpu_w_match and "mW" not in line:
                current["cpu"] = float(cpu_w_match.group(1))

            # Separator between samples
            if line.startswith("*****") and current:
                self._samples.append(current.copy())
                current = {}

        # Capture last partial sample
        if current:
            self._samples.append(current)
