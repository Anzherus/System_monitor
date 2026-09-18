import asyncio, logging, os, re
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, Iterable, List
from modules.parser import iter_log_file

logger = logging.getLogger(__name__)


# Sequential
def process_sequential(files: Iterable[str]) -> int:
    total = 0
    for path in files:
        for _ in iter_log_file(path):
            total += 1
    return total


# I/O
def process_threads(files: Iterable[str], workers: int = 8) -> int:
    files = list(files)
    total = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for count in ex.map(_count_file, files):
            total += count
    return total


def _count_file(path: str) -> int:
    return sum(1 for _ in iter_log_file(path))


# asyncio
async def _async_count(path: str) -> int:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _count_file, path)


async def _async_process(files: List[str]) -> int:
    tasks = [asyncio.create_task(_async_count(p)) for p in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return sum(r for r in results if isinstance(r, int))


def process_asyncio(files: Iterable[str]) -> int:
    files = list(files)
    return asyncio.run(_async_process(files))


# Multiprocessing
def _heavy_analysis(path: str) -> dict:
    cpu_re = re.compile(r"CPU usage:\s(\d+)")
    total = 0
    cpu_sum = 0.0
    cpu_count = 0
    for rec in iter_log_file(path):
        total += 1
        m = cpu_re.search(rec["message"])
        if m:
            cpu_sum += float(m.group(1))
            cpu_count += 1
    return {"total": total, "cpu_sum": cpu_sum, "cpu_count": cpu_count}


def process_multiprocessing(files: Iterable[str], workers: int = 4) -> dict:
    files = list(files)
    agg = {"total": 0, "cpu_sum": 0.0, "cpu_count": 0}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(_heavy_analysis, files):
            agg["total"] += res["total"]
            agg["cpu_sum"] += res["cpu_sum"]
            agg["cpu_count"] += res["cpu_count"]
    return agg