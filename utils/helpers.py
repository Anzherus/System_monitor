import functools
import itertools
import logging
import time
from collections import deque
from contextlib import contextmanager
from typing import Iterable, Iterator

logger = logging.getLogger(__name__)


class LogRecordIterator:
    def __init__(self, records, page_size: int = 100):
        self._records = iter(records)
        self._page_size = max(1, page_size)
        self._buffer: deque = deque()

    def __iter__(self):
        return self

    def __next__(self):
        if not self._buffer:
            chunk = list(itertools.islice(self._records, self._page_size))
            if not chunk:
                raise StopIteration
            self._buffer.extend(chunk)
        return self._buffer.popleft()


def chain_files(file_iterables):
    return itertools.chain.from_iterable(file_iterables)


def detect_floods(records, min_run: int = 5):
    key = lambda r: (r.get("server"), r.get("message"))
    for (srv, msg), grp in itertools.groupby(records, key=key):
        n = sum(1 for _ in grp)
        if n >= min_run:
            yield {"server": srv, "message": msg, "count": n}


@functools.lru_cache(maxsize=16)
def cached_severity_weight(level):
    return {"INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}.get(level, 0)


def severity_total(level_counts):
    return functools.reduce(
        lambda acc, kv: acc + cached_severity_weight(kv[0]) * kv[1],
        level_counts.items(),
        0,
    )


def format_record(prefix, record):
    base = (f"{record.get('date', '?')} "
            f"{str(record.get('time', '?'))[:8]} | "
            f"{record.get('server', '?'):>12} | "
            f"{record.get('level', '?'):<8} | "
            f"{record.get('message', '')}")
    return f"{prefix} {base}" if prefix else base



format_error = functools.partial(format_record, "[ERR]")


@contextmanager
def timer(label: str = ""):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info("%s: %.2f сек", label or "timer", elapsed)