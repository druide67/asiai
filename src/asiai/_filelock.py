"""Shared ``fcntl.flock`` helper used by config files holding read-modify-write state.

Factored out of ``asiai.auth.config`` and ``asiai.fleet.config`` so the
behavior stays in sync: best-effort cross-process exclusive lock with a
silent fallback when the FS does not support ``flock`` (rare on local
macOS/Linux disks, common on some NFS configurations).

Why best-effort: the worst case without flock is the pre-existing race
(``rotate_token`` vs ``upsert_node`` losing an entry). Returning success
instead of crashing keeps the CLI usable on filesystems where flock
returns ``OperationalError`` — at the cost of an unobservable window
during concurrent writes.
"""

from __future__ import annotations

import contextlib
import fcntl
import logging
import os
from collections.abc import Iterator

logger = logging.getLogger("asiai._filelock")


@contextlib.contextmanager
def file_lock(lock_path: str, *, parent_dir: str | None = None) -> Iterator[None]:
    """Acquire an exclusive ``flock`` on ``lock_path`` for the body.

    The lock file is created with ``0o600`` perms; the parent directory
    is created if it does not exist. If creation fails the context still
    yields (best-effort: the caller's save will surface the real error).
    Failures to actually take the flock log a warning at ``info`` level
    so an operator running ``asiai`` over NFS can see why their concurrent
    edit dropped an entry without scaring them off the tool.
    """
    if parent_dir is None:
        parent_dir = os.path.dirname(lock_path) or "."
    try:
        os.makedirs(parent_dir, exist_ok=True)
    except OSError:
        yield
        return
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        yield
        return
    locked = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            locked = True
        except OSError as e:
            logger.info(
                "flock(LOCK_EX) failed on %s: %s — falling back to unlocked path",
                lock_path,
                e,
            )
        yield
    finally:
        if locked:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)
