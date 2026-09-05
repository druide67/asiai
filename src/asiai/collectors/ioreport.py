"""Power monitoring via IOReport Energy Model (macOS, no sudo).

Reads GPU, CPU, ANE, DRAM and DCS (DRAM-controller) power consumption from
Apple's IOReport framework using ctypes bindings to ``libIOReport.dylib``.
This is the same data source as ``powermetrics`` but accessible without
elevated privileges. Per-rail energy (Joules) over each interval is exposed
alongside watts so callers can compute energy-per-token.

Validated on M4 Pro: <1.5% delta vs ``sudo powermetrics`` on both
LM Studio (MLX) and Ollama (llama.cpp) under inference load.

Usage::

    sampler = IOReportSampler()
    time.sleep(1)
    reading = sampler.sample()
    print(f"GPU: {reading.gpu_watts}W")
    sampler.close()
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger("asiai.collectors.ioreport")

# CoreFoundation encoding
_CF_STRING_ENCODING_UTF8 = 0x08000100

# Lazy-loaded library handles
_iorep = None
_cf = None
_dict_tid: int = 0
_available: bool | None = None
# Interned CFString for the IOReportChannels dictionary key — created once
# (a per-sample _cfstr() here used to leak one CFString per cycle).
_key_ioreport_channels: ctypes.c_void_p | None = None


def ioreport_available() -> bool:
    """Return True if IOReport energy channels are accessible."""
    global _available
    if _available is not None:
        return _available
    try:
        _load_libs()
        _available = True
    except Exception:
        _available = False
    return _available


def _load_libs() -> None:
    """Load libIOReport and CoreFoundation, set up function signatures."""
    global _iorep, _cf, _dict_tid

    if _iorep is not None:
        return

    _iorep = ctypes.cdll.LoadLibrary("/usr/lib/libIOReport.dylib")
    _cf = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
    )

    # IOReport signatures
    _iorep.IOReportCopyChannelsInGroup.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint64,
        ctypes.c_uint64,
        ctypes.c_uint64,
    ]
    _iorep.IOReportCopyChannelsInGroup.restype = ctypes.c_void_p

    _iorep.IOReportCreateSubscription.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint64,
        ctypes.c_void_p,
    ]
    _iorep.IOReportCreateSubscription.restype = ctypes.c_void_p

    _iorep.IOReportCreateSamples.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    _iorep.IOReportCreateSamples.restype = ctypes.c_void_p

    _iorep.IOReportCreateSamplesDelta.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    _iorep.IOReportCreateSamplesDelta.restype = ctypes.c_void_p

    _iorep.IOReportSimpleGetIntegerValue.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int32,
    ]
    _iorep.IOReportSimpleGetIntegerValue.restype = ctypes.c_int64

    _iorep.IOReportChannelGetChannelName.argtypes = [ctypes.c_void_p]
    _iorep.IOReportChannelGetChannelName.restype = ctypes.c_void_p

    _iorep.IOReportChannelGetUnitLabel.argtypes = [ctypes.c_void_p]
    _iorep.IOReportChannelGetUnitLabel.restype = ctypes.c_void_p

    # CoreFoundation signatures
    _cf.CFStringCreateWithCString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_uint32,
    ]
    _cf.CFStringCreateWithCString.restype = ctypes.c_void_p

    _cf.CFStringGetCStringPtr.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _cf.CFStringGetCStringPtr.restype = ctypes.c_char_p

    _cf.CFStringGetCString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_long,
        ctypes.c_uint32,
    ]
    _cf.CFStringGetCString.restype = ctypes.c_bool

    _cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
    _cf.CFArrayGetCount.restype = ctypes.c_long

    _cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
    _cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p

    _cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _cf.CFDictionaryGetValue.restype = ctypes.c_void_p

    _cf.CFGetTypeID.argtypes = [ctypes.c_void_p]
    _cf.CFGetTypeID.restype = ctypes.c_ulong

    _cf.CFDictionaryGetTypeID.restype = ctypes.c_ulong

    _cf.CFRelease.argtypes = [ctypes.c_void_p]
    _cf.CFRelease.restype = None

    _dict_tid = _cf.CFDictionaryGetTypeID()

    global _key_ioreport_channels
    _key_ioreport_channels = _cfstr("IOReportChannels")


def _cfstr(s: str) -> ctypes.c_void_p:
    """Create a CFString from a Python string."""
    return _cf.CFStringCreateWithCString(None, s.encode(), _CF_STRING_ENCODING_UTF8)


def _cfstr_to_str(cfs: ctypes.c_void_p) -> str | None:
    """Convert a CFString to Python string, with fallback."""
    if not cfs:
        return None
    r = _cf.CFStringGetCStringPtr(cfs, _CF_STRING_ENCODING_UTF8)
    if r:
        return r.decode()
    buf = ctypes.create_string_buffer(256)
    if _cf.CFStringGetCString(cfs, buf, 256, _CF_STRING_ENCODING_UTF8):
        return buf.value.decode()
    return None


def _cfrelease(obj) -> None:
    """CFRelease a Create/Copy-rule object; safe on NULL/None."""
    if obj:
        _cf.CFRelease(obj)


def _unwrap_to_array(obj: ctypes.c_void_p) -> ctypes.c_void_p:
    """Extract IOReportChannels CFArray from a CFDictionary result.

    The returned array follows the Get rule (owned by ``obj``) — callers
    must not release it, and must keep ``obj`` alive while using it.
    """
    if _cf.CFGetTypeID(obj) == _dict_tid:
        return _cf.CFDictionaryGetValue(obj, _key_ioreport_channels)
    return obj


# Energy channel names we care about (lowercase for matching).
# Channel names verified by enumeration on M5 Max (`Energy Model` group):
# GPU SRAM has no separate rail there (folded into `GPU`), and DCS is the
# DRAM-controller subsystem (~2 W idle) that GPU-only power badly omits.
_CHANNEL_MAP = {
    "cpu energy": "cpu",
    "gpu": "gpu",
    "gpu energy": "gpu_nj",  # nJ aggregate, converted separately
    "ane": "ane",
    "dram": "dram",
    "dcs": "dcs",
    # Read since 2026-09-02, NOT yet part of soc_watts: the memory-cache
    # controller and the fabric. On an M5 Max at idle they add +29 % to the
    # five rails above; on an M4 Pro +49 %. Both move with memory traffic, i.e.
    # with exactly the decode we measure. Whether they join the published base
    # (soc5 → soc7) is decided on measurements under load, not here.
    "amcc": "amcc",
    "fab": "fab",
}

# Rails without which a package figure is NOT a package figure. ANE is read but
# optional (it idles at 0 W on every chip measured); AMCC/FAB optional until the
# base decision. A missing required rail makes soc_watts None — never a smaller
# number: on 2026-09-02 an M4 Pro exposed rails under other names and the
# five-rail sum came out as 54 % of the package with no error anywhere.
_REQUIRED_RAILS = frozenset({"gpu", "cpu", "dram", "dcs"})

# Unit divisors to convert raw energy to joules. Plain "J" was missing: a rail
# reported in Joules was silently dropped (read as absent).
_UNIT_DIVISORS = {
    "J": 1.0,
    "mJ": 1_000.0,
    "uJ": 1_000_000.0,
    "nJ": 1_000_000_000.0,
}


@dataclass
class IOReportReading:
    """Raw power reading from IOReport Energy Model.

    Watts are the mean over the sampling interval; the matching ``*_joules``
    are the absolute energy consumed during it. ``soc_watts`` / ``soc_joules``
    add the DRAM-controller (DCS) rail to the GPU+CPU+ANE+DRAM total — the
    honest package figure for a memory-bound decode on unified memory, where
    GPU-only power badly undercounts.
    """

    gpu_watts: float = 0.0
    cpu_watts: float = 0.0
    ane_watts: float = 0.0
    dram_watts: float = 0.0
    dcs_watts: float = 0.0
    amcc_watts: float = 0.0
    fab_watts: float = 0.0
    gpu_joules: float = 0.0
    cpu_joules: float = 0.0
    ane_joules: float = 0.0
    dram_joules: float = 0.0
    dcs_joules: float = 0.0
    amcc_joules: float = 0.0
    fab_joules: float = 0.0
    interval_s: float = 0.0
    # Rails actually read with a known unit. A rail at 0 J that WAS read (ANE at
    # idle) is present; a rail that never appeared, or came with an unknown unit,
    # is absent. The two used to be indistinguishable — both read as 0.0.
    rails_present: frozenset[str] = frozenset()

    @property
    def total_watts(self) -> float:
        """Legacy SoC estimate WITHOUT the DRAM-controller rail.

        Kept for backward compatibility; new code should prefer ``soc_watts``.
        """
        return self.gpu_watts + self.cpu_watts + self.ane_watts + self.dram_watts

    @property
    def has_required_rails(self) -> bool:
        gpu_ok = "gpu" in self.rails_present or "gpu_nj" in self.rails_present
        return gpu_ok and (_REQUIRED_RAILS - {"gpu"}) <= self.rails_present

    @property
    def soc_watts(self) -> float | None:
        """Package power over the five named rails (compute + DRAM + DCS).

        None when a required rail was not read: a package figure missing a
        rail is not a smaller package figure, it is a different quantity.
        """
        if not self.has_required_rails:
            return None
        return self.total_watts + self.dcs_watts

    @property
    def soc7_watts(self) -> float | None:
        """soc_watts plus the memory-cache controller and fabric rails.

        Candidate published base (decision pending measurements under load);
        None when soc_watts is None or when either extra rail was not read.
        """
        base = self.soc_watts
        if base is None or not {"amcc", "fab"} <= self.rails_present:
            return None
        return base + self.amcc_watts + self.fab_watts

    @property
    def soc_joules(self) -> float | None:
        """Energy over the interval summed across the five named rails."""
        if not self.has_required_rails:
            return None
        return (
            self.gpu_joules + self.cpu_joules + self.ane_joules + self.dram_joules + self.dcs_joules
        )


class IOReportSampler:
    """Reads power data from IOReport Energy Model without sudo.

    Creates a subscription once and reuses it for all subsequent samples.
    Each call to :meth:`sample` takes a new IOReport sample, computes the
    energy delta since the previous sample, and converts to watts.

    Usage::

        sampler = IOReportSampler()
        time.sleep(1)           # minimum meaningful interval
        reading = sampler.sample()
        print(f"GPU: {reading.gpu_watts:.1f}W")
        sampler.close()
    """

    def __init__(self) -> None:
        _load_libs()

        # Serializes sample()/close(): the instance is shared across threads
        # (web SSE connections + API routes hit one singleton), and the
        # read-modify-write of _prev_sample/_prev_time must not interleave.
        self._lock = threading.Lock()

        group_name = _cfstr("Energy Model")
        try:
            channels = _iorep.IOReportCopyChannelsInGroup(
                group_name,
                None,
                0,
                0,
                0,
            )
        finally:
            _cfrelease(group_name)
        if not channels:
            raise RuntimeError("IOReportCopyChannelsInGroup returned NULL")

        self._sub_channels = ctypes.c_void_p()
        self._subscription = _iorep.IOReportCreateSubscription(
            None,
            channels,
            ctypes.byref(self._sub_channels),
            0,
            None,
        )
        # The subscription keeps what it needs in _sub_channels; the
        # Copy-rule channel list is ours to release.
        _cfrelease(channels)
        if not self._subscription:
            raise RuntimeError("IOReportCreateSubscription returned NULL")

        # Take initial sample as baseline
        self._prev_sample = _iorep.IOReportCreateSamples(
            self._subscription,
            self._sub_channels,
            None,
        )
        self._prev_time = time.monotonic()

        if not self._prev_sample:
            raise RuntimeError("IOReportCreateSamples returned NULL")

        logger.debug("IOReport Energy Model subscription created")

    def sample(self) -> IOReportReading:
        """Take a new sample and return watts since previous sample."""
        with self._lock:
            return self._sample_locked()

    def _sample_locked(self) -> IOReportReading:
        now_sample = _iorep.IOReportCreateSamples(
            self._subscription,
            self._sub_channels,
            None,
        )
        now_time = time.monotonic()
        interval = now_time - self._prev_time

        if not now_sample or interval <= 0:
            _cfrelease(now_sample)
            return IOReportReading()

        delta = _iorep.IOReportCreateSamplesDelta(
            self._prev_sample,
            now_sample,
            None,
        )
        _cfrelease(self._prev_sample)
        self._prev_sample = now_sample
        self._prev_time = now_time

        if not delta:
            return IOReportReading()
        try:
            return self._read_delta(delta, interval)
        finally:
            _cfrelease(delta)

    @staticmethod
    def _iter_channels(delta):
        """Yield ``(name, unit_label, raw_int)`` for every channel in a delta.

        This is the one place that touches CoreFoundation for channel data; it
        exists as a seam so ``_read_delta`` can be exercised with a plain list
        of tuples in tests, without hardware. Names come back as read (case
        preserved); ``unit_label`` may be None when the CFString conversion
        fails, and callers must treat that as an unknown unit.
        """
        arr = _unwrap_to_array(delta)
        if not arr:
            return
        n = _cf.CFArrayGetCount(arr)
        for i in range(n):
            item = _cf.CFArrayGetValueAtIndex(arr, i)
            name = _cfstr_to_str(_iorep.IOReportChannelGetChannelName(item))
            if not name:
                continue
            unit = _cfstr_to_str(_iorep.IOReportChannelGetUnitLabel(item))
            raw = _iorep.IOReportSimpleGetIntegerValue(item, 0)
            yield name, unit, raw

    def _read_delta(self, delta, interval: float) -> IOReportReading:
        return self._reading_from_channels(self._iter_channels(delta), interval)

    @staticmethod
    def _reading_from_channels(channels, interval: float) -> IOReportReading:
        """Build a reading from ``(name, unit, raw)`` tuples — pure, testable."""
        w: dict[str, float] = {}
        j: dict[str, float] = {}
        present: set[str] = set()

        for name, unit, raw in channels:
            key = _CHANNEL_MAP.get(name.lower())
            if not key:
                continue

            divisor = _UNIT_DIVISORS.get(unit)
            if divisor is None:
                # Unknown / None unit label (e.g. a failed CFString conversion):
                # the rail is NOT read — mark it absent rather than assume Joules
                # (divisor 1.0 would inflate mJ/uJ/nJ by up to 1e9x) and rather
                # than leave it at 0.0 (which reads as "idle", not "unknown").
                continue
            joules = raw / divisor
            watts = joules / interval

            if key == "gpu_nj":
                # nJ aggregate: used only if the mJ channel is absent, but its
                # presence is recorded so an export can show which one served.
                present.add("gpu_nj")
                if "gpu" not in present:
                    w["gpu"], j["gpu"] = watts, joules
                continue
            present.add(key)
            w[key], j[key] = watts, joules

        return IOReportReading(
            gpu_watts=round(w.get("gpu", 0.0), 2),
            cpu_watts=round(w.get("cpu", 0.0), 2),
            ane_watts=round(w.get("ane", 0.0), 3),
            dram_watts=round(w.get("dram", 0.0), 2),
            dcs_watts=round(w.get("dcs", 0.0), 2),
            amcc_watts=round(w.get("amcc", 0.0), 2),
            fab_watts=round(w.get("fab", 0.0), 2),
            gpu_joules=round(j.get("gpu", 0.0), 3),
            cpu_joules=round(j.get("cpu", 0.0), 3),
            ane_joules=round(j.get("ane", 0.0), 4),
            dram_joules=round(j.get("dram", 0.0), 3),
            dcs_joules=round(j.get("dcs", 0.0), 3),
            amcc_joules=round(j.get("amcc", 0.0), 3),
            fab_joules=round(j.get("fab", 0.0), 3),
            interval_s=round(interval, 3),
            rails_present=frozenset(present),
        )

    def close(self) -> None:
        """Release the subscription, its channel dictionary and the baseline sample."""
        with self._lock:
            _cfrelease(self._prev_sample)
            self._prev_sample = None
            _cfrelease(self._sub_channels)
            self._sub_channels = ctypes.c_void_p()
            _cfrelease(self._subscription)
            self._subscription = None
        logger.debug("IOReport sampler closed")

    def __enter__(self) -> IOReportSampler:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
