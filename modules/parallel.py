"""
Параллельная обработка логов.
"""
import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Iterable, List

from modules.analyzer import extract_metrics
from modules.parser import iter_log_file

logger = logging.getLogger(__name__)


def _analyze_file(path: str) -> dict:
    total = 0
    cpu_sum = 0.0
    cpu_count = 0
    for rec in iter_log_file(path):
        total += 1
        v = extract_metrics(rec.get("message", "")).get("cpu")
        if v is not None:
            cpu_sum += v
            cpu_count += 1
    return {"total": total, "cpu_sum": cpu_sum, "cpu_count": cpu_count}


def _empty() -> dict:
    return {"total": 0, "cpu_sum": 0.0, "cpu_count": 0}


def _merge(agg: dict, res: dict) -> None:
    agg["total"] += res["total"]
    agg["cpu_sum"] += res["cpu_sum"]
    agg["cpu_count"] += res["cpu_count"]

#Принудительно читает файлы для того, чтобы они оказались в оперативной памяти.. для того чтобы они тянулись оттуда а не с диска

def warmup_cache(files: Iterable[str]) -> None:
    for path in files:
        try:
            with open(path, "rb") as f:
                while f.read(1 << 20):
                    pass
        except OSError:
            pass


def process_sequential(files: Iterable[str]) -> dict:
    agg = _empty()
    for path in files:
        _merge(agg, _analyze_file(path))
    return agg


def process_threads(files: Iterable[str], workers: int = 8) -> dict:
    files = list(files)
    agg = _empty()
    workers = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(_analyze_file, files):
            _merge(agg, res)
    return agg


async def _async_analyze(path: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _analyze_file, path)


async def _async_process(files: List[str], concurrency: int = 8) -> dict:
    sem = asyncio.Semaphore(max(1, int(concurrency)))
    tasks = [asyncio.create_task(_async_analyze(p, sem)) for p in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    agg = _empty()
    for r in results:
        if isinstance(r, dict):
            _merge(agg, r)
        else:
            logger.warning("Asyncio tassk failed: %s", r)
    return agg


def process_asyncio(files: Iterable[str], concurrency: int = 8) -> dict:
    return asyncio.run(_async_process(list(files), concurrency))


def process_multiprocessing(files: Iterable[str], workers: int = 4) -> dict:
    files = list(files)
    workers = max(1, int(workers))
    agg = _empty()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(_analyze_file, files):
            _merge(agg, res)
    return agg