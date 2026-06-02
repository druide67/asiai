# Known issues

Tracked defects that are deliberately deferred (low impact, or a fix carries
more risk than the bug). Each entry says why it's open and what a fix would take.

## ioreport: CFString leak in `_unwrap_to_array` (low)

`asiai/collectors/ioreport.py` calls `_cfstr("IOReportChannels")` on every
`IOReportSampler.sample()` (via `_unwrap_to_array`). `CFStringCreateWithCString`
returns an owned reference (CoreFoundation Create Rule) that is never released,
so each sample leaks one small CFString (~tens of bytes). Pre-existing, not
introduced by the 1.11.0 overhaul.

- **Impact**: a slow leak over a long bench (thousands of samples). Negligible
  for normal runs; matters only for a very long-lived monitor process.
- **Why deferred**: the fix needs a `CFRelease` ctypes binding, and releasing the
  wrong object segfaults the process. Not worth that risk inside the 1.11.0
  metrics work.
- **Fix sketch**: bind `CFRelease` (`argtypes=[c_void_p]`), cache the
  `"IOReportChannels"` CFString once at module load instead of recreating it per
  call, and release any CFStrings created per sample. Cover with a soak test.

## agentic: `_compute_reuse` and `_compute_verdict` use different early-stop filters (low)

`asiai/benchmark/agentic.py`: the legacy categorical `_compute_verdict` filters
runs on `error is None` only, while `_compute_reuse` additionally excludes
early-stopped runs. On a run set containing early-stops the published
`prefix_cache_reuse_verdict` (string) and the `prefix_cache_reuse.reuse_fraction`
can therefore be computed over slightly different run subsets.

- **Impact**: cosmetic. The verdict is explicitly tagged engine-family-specific
  and consumers are told to use the raw `reuse_fraction` signal, not the verdict.
- **Why deferred**: aligning the filters changes the legacy verdict's value on
  early-stop runs; no real decision depends on it.
- **Fix sketch**: have `_compute_verdict` reuse the same early-stop exclusion as
  `_compute_reuse` (factor the `_ok(run)` predicate out and share it).
