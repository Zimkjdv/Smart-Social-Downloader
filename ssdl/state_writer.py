"""Owned, bounded snapshot writer; no application or queue lock is used during I/O."""
from __future__ import annotations

from types import MappingProxyType
import math
import threading
import time

CHECKPOINT_SECONDS = 0.5
SAVE_ERROR = "本機紀錄保存失敗，變更目前只在記憶體中；請檢查磁碟權限與空間後重新嘗試保存。"
_SCALARS = {str, int, float, bool, type(None)}


class ScalarArray(tuple):
    """Frozen scalar lists share immutable strings, never their mutable container."""


def freeze_snapshot(value):
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("State snapshot keys must be strings")
        return MappingProxyType({key: freeze_snapshot(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        if all(type(item) in _SCALARS for item in value):
            return ScalarArray(value)
        return tuple(freeze_snapshot(item) for item in value)
    if type(value) in _SCALARS:
        return value
    raise TypeError("State snapshot must contain JSON values")


def thaw_snapshot(value):
    if isinstance(value, MappingProxyType):
        return {key: thaw_snapshot(item) for key, item in value.items()}
    if isinstance(value, ScalarArray):
        return list(value)
    if isinstance(value, tuple):
        return [thaw_snapshot(item) for item in value]
    return value


class StateWriter:
    """At most one in-flight and one replaceable pending immutable snapshot.

    Constructing does not start a thread. start()/submit() explicitly start it;
    wait() is a durability barrier and must be called outside the queue condition.
    Failed latest state stays pending without a busy retry loop. A new submission
    or closing flush makes one new attempt; a failed close returns False.
    """
    def __init__(self, save, failed, *, checkpoint_seconds=CHECKPOINT_SECONDS):
        if type(checkpoint_seconds) not in {int, float} or not math.isfinite(checkpoint_seconds) or not 0 <= checkpoint_seconds <= 60:
            raise ValueError("Invalid checkpoint interval")
        self._save, self._failed = save, failed
        self._checkpoint_seconds = checkpoint_seconds
        self._condition = threading.Condition()
        self._thread = None
        self._generation = self._saved_generation = self._failed_generation = 0
        self._pending = None
        self._inflight = 0
        self._due = 0.0
        self._retry_required = False
        self._closing = self._closed = False
        self._writes = self._coalesced = 0

    def _start_locked(self):
        if self._closing or self._closed:
            raise RuntimeError("State writer is closed")
        if self._thread is None:
            thread = threading.Thread(target=self._run, name="state-writer", daemon=True)
            try:
                thread.start()
            except BaseException:
                self._thread = None
                raise
            self._thread = thread

    def start(self):
        with self._condition:
            self._start_locked()

    def submit(self, snapshot, *, checkpoint=False):
        if not isinstance(snapshot, MappingProxyType):
            raise TypeError("Submit an immutable snapshot")
        with self._condition:
            self._start_locked()
            self._generation += 1
            if self._pending is None:
                self._due = time.monotonic() + self._checkpoint_seconds if checkpoint else 0
            else:
                self._coalesced += 1
            if not checkpoint:
                self._due = 0
            self._pending = (self._generation, snapshot)
            self._retry_required = False
            self._condition.notify_all()
            return self._generation

    def reject_snapshot(self):
        """Keep an invalid capture visibly dirty even if an older write succeeds."""
        with self._condition:
            if self._closing or self._closed:
                raise RuntimeError("State writer is closed")
            self._generation += 1
            self._failed_generation = self._generation
            self._condition.notify_all()
            generation = self._generation
        self._failed()
        return generation

    def wait(self, generation):
        with self._condition:
            if type(generation) is not int or not 0 <= generation <= self._generation:
                raise ValueError("Invalid state generation")
            # Critical callers can also flush a coalesced progress checkpoint.
            if self._pending is not None and not self._retry_required:
                self._due = 0
                self._condition.notify_all()
            while self._saved_generation < generation:
                if self._closed or self._thread is None or not self._thread.is_alive():
                    return False
                if self._failed_generation >= generation:
                    can_complete = self._inflight >= generation or (
                        self._pending is not None and self._pending[0] >= generation and not self._retry_required)
                    if not can_complete:
                        return False
                self._condition.wait()
            return True

    def status(self):
        with self._condition:
            return {"generation": self._generation, "saved_generation": self._saved_generation,
                    "failed_generation": self._failed_generation,
                    "pending": self._saved_generation < self._generation,
                    "writer_running": bool(self._thread and self._thread.is_alive()),
                    "writer_closed": self._closed, "writes": self._writes, "coalesced": self._coalesced}

    def _run(self):
        try:
            while True:
                with self._condition:
                    while self._pending is None or self._retry_required or time.monotonic() < self._due:
                        if self._closing and (self._pending is None or self._retry_required):
                            return
                        timeout = max(0, self._due - time.monotonic()) if self._pending and not self._retry_required else None
                        self._condition.wait(timeout)
                    generation, snapshot = self._pending
                    self._pending = None
                    self._inflight = generation
                try:
                    saved = self._save(snapshot) is True
                except Exception:
                    saved = False
                if not saved:
                    try:
                        self._failed()
                    except Exception:
                        pass  # Generation failure still remains visible via status().
                with self._condition:
                    self._inflight = 0
                    self._writes += 1
                    if saved:
                        self._saved_generation = generation
                    else:
                        self._failed_generation = max(self._failed_generation, generation)
                        if self._pending is None:
                            self._pending = (generation, snapshot)
                            self._retry_required = True
                    self._condition.notify_all()
                del snapshot  # Do not retain a completed large history while idle.
        finally:
            with self._condition:
                if self._saved_generation < self._generation:
                    self._failed_generation = max(self._failed_generation, self._generation)
                self._closed = True
                self._condition.notify_all()

    def close(self):
        with self._condition:
            if not self._closing and not self._closed:
                self._closing = True
                self._due = 0
                self._retry_required = False  # One last flush, including dirty state.
                if self._thread is None:
                    self._closed = True
                self._condition.notify_all()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()
        with self._condition:
            return self._saved_generation >= self._generation
