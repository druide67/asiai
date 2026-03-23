"""Power monitoring via IOReport Energy Model (macOS, no sudo).

Reads GPU, CPU, ANE and DRAM power consumption from Apple's IOReport
framework using ctypes bindings to ``libIOReport.dylib``. This is the
same data source as ``powermetrics`` but accessible without elevated
privileges.

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
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64,
    ]
    _iorep.IOReportCopyChannelsInGroup.restype = ctypes.c_void_p

    _iorep.IOReportCreateSubscription.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint64, ctypes.c_void_p,
    ]
    _iorep.IOReportCreateSubscription.restype = ctypes.c_void_p

    _iorep.IOReportCreateSamples.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ]
    _iorep.IOReportCreateSamples.restype = ctypes.c_void_p

    _iorep.IOReportCreateSamplesDelta.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ]
    _iorep.IOReportCreateSamplesDelta.restype = ctypes.c_void_p

    _iorep.IOReportSimpleGetIntegerValue.argtypes = [
        ctypes.c_void_p, ctypes.c_int32,
    ]
    _iorep.IOReportSimpleGetIntegerValue.restype = ctypes.c_int64

    _iorep.IOReportChannelGetChannelName.argtypes = [ctypes.c_void_p]
    _iorep.IOReportChannelGetChannelName.restype = ctypes.c_void_p

    _iorep.IOReportChannelGetUnitLabel.argtypes = [ctypes.c_void_p]
    _iorep.IOReportChannelGetUnitLabel.restype = ctypes.c_void_p

    # CoreFoundation signatures
    _cf.CFStringCreateWithCString.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32,
    ]
    _cf.CFStringCreateWithCString.restype = ctypes.c_void_p

    _cf.CFStringGetCStringPtr.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _cf.CFStringGetCStringPtr.restype = ctypes.c_char_p

    _cf.CFStringGetCString.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32,
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

    _dict_tid = _cf.CFDictionaryGetTypeID()


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


def _unwrap_to_array(obj: ctypes.c_void_p) -> ctypes.c_void_p:
    """Extract IOReportChannels CFArray from a CFDictionary result."""
    if _cf.CFGetTypeID(obj) == _dict_tid:
        return _cf.CFDictionaryGetValue(obj, _cfstr("IOReportChannels"))
    return obj


# Energy channel names we care about (lowercase for matching)
_CHANNEL_MAP = {
    "cpu energy": "cpu",
    "gpu": "gpu",
    "gpu energy": "gpu_nj",  # nJ aggregate, converted separately
    "ane": "ane",
    "dram": "dram",
}

# Unit divisors to convert raw energy to joules
_UNIT_DIVISORS = {
    "mJ": 1_000.0,
    "uJ": 1_000_000.0,
    "nJ": 1_000_000_000.0,
}


@dataclass
class IOReportReading:
    """Raw power reading from IOReport Energy Model."""

    gpu_watts: float = 0.0
    cpu_watts: float = 0.0
    ane_watts: float = 0.0
    dram_watts: float = 0.0
    interval_s: float = 0.0

    @property
    def total_watts(self) -> float:
        return self.gpu_watts + self.cpu_watts + self.ane_watts + self.dram_watts


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

        channels = _iorep.IOReportCopyChannelsInGroup(
            _cfstr("Energy Model"), None, 0, 0, 0,
        )
        if not channels:
            raise RuntimeError("IOReportCopyChannelsInGroup returned NULL")

        self._sub_channels = ctypes.c_void_p()
        self._subscription = _iorep.IOReportCreateSubscription(
            None, channels, ctypes.byref(self._sub_channels), 0, None,
        )
        if not self._subscription:
            raise RuntimeError("IOReportCreateSubscription returned NULL")

        # Take initial sample as baseline
        self._prev_sample = _iorep.IOReportCreateSamples(
            self._subscription, self._sub_channels, None,
        )
        self._prev_time = time.monotonic()

        if not self._prev_sample:
            raise RuntimeError("IOReportCreateSamples returned NULL")

        logger.debug("IOReport Energy Model subscription created")

    def sample(self) -> IOReportReading:
        """Take a new sample and return watts since previous sample."""
        now_sample = _iorep.IOReportCreateSamples(
            self._subscription, self._sub_channels, None,
        )
        now_time = time.monotonic()
        interval = now_time - self._prev_time

        if not now_sample or interval <= 0:
            return IOReportReading()

        delta = _iorep.IOReportCreateSamplesDelta(
            self._prev_sample, now_sample, None,
        )
        self._prev_sample = now_sample
        self._prev_time = now_time

        if not delta:
            return IOReportReading()

        arr = _unwrap_to_array(delta)
        if not arr:
            return IOReportReading()

        n = _cf.CFArrayGetCount(arr)

        gpu_watts = 0.0
        cpu_watts = 0.0
        ane_watts = 0.0
        dram_watts = 0.0

        for i in range(n):
            item = _cf.CFArrayGetValueAtIndex(arr, i)
            name = _cfstr_to_str(
                _iorep.IOReportChannelGetChannelName(item),
            )
            if not name:
                continue

            key = _CHANNEL_MAP.get(name.lower())
            if not key:
                continue

            unit = _cfstr_to_str(
                _iorep.IOReportChannelGetUnitLabel(item),
            )
            raw = _iorep.IOReportSimpleGetIntegerValue(item, 0)

            divisor = _UNIT_DIVISORS.get(unit, 1.0)
            watts = (raw / divisor) / interval

            if key == "gpu":
                gpu_watts = watts
            elif key == "gpu_nj":
                # Only use nJ aggregate if mJ channel not found
                if gpu_watts == 0.0:
                    gpu_watts = watts
            elif key == "cpu":
                cpu_watts = watts
            elif key == "ane":
                ane_watts = watts
            elif key == "dram":
                dram_watts = watts

        return IOReportReading(
            gpu_watts=round(gpu_watts, 2),
            cpu_watts=round(cpu_watts, 2),
            ane_watts=round(ane_watts, 3),
            dram_watts=round(dram_watts, 2),
            interval_s=round(interval, 3),
        )

    def close(self) -> None:
        """Release resources."""
        self._subscription = None
        self._sub_channels = ctypes.c_void_p()
        self._prev_sample = None
        logger.debug("IOReport sampler closed")

    def __enter__(self) -> IOReportSampler:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
