import functools, itertools, time
from contextlib import contextmanager
from typing import Iterable, Iterator, List, Tuple


class LogRecordIterator:
    def __init__(self, records: Iterable[dict], page_size: int = 100):
        self._records = records
        self._page_size = page_size
        self._index = 0
        self._buffer: List[dict] = []

    def __iter__(self) -> "LogRecordIterator":
        return self

    def __next__(self) -> dict:
        if not self._buffer:
            chunk = list(itertools.islice(self._records, self._page_size))
            if not chunk:
                raise StopIteration
            self._buffer = chunk
        return self._buffer.pop(0)


def chain_files(file_iterables: Iterable[Iterable[dict]]) -> Iterator[dict]:
    return itertools.chain.from_iterable(file_iterables)


def group_by_level(records: Iterable[dict]) -> Iterator[Tuple[str, Iterator[dict]]]:
    key = lambda r: r.get("level", "UNKNOWN")
    for level, group in itertools.groupby(records, key=key):
        yield level, group


@functools.lru_cache(maxsize=128)
def cached_severity_weight(level: str) -> int:
    return {"INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}.get(level, 0)


def total_weight(records: Iterable[dict]) -> int:
    return functools.reduce(lambda acc, r: acc + cached_severity_weight(r.get("level", "")), records, 0)


def format_record(prefix: str, record: dict) -> str:
    return f"{prefix} {record.get('server', '?')} | {record.get('level', '?')}"


format_error = functools.partial(format_record, "[ERR]")


@contextmanager
def timer(label: str = ""):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed:.2f} сек")