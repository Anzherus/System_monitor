"""Сравнение производительности методов обработки."""
import logging, random, time
from config import Settings
from modules.logs import LogManager
from modules.parallel import (
    process_asyncio,
    process_multiprocessing,
    process_sequential,
    process_threads,
    warmup_cache,
)

logger = logging.getLogger(__name__)


def run_benchmark(settings: Settings) -> dict:
    files = LogManager(settings.logs_path).files()
    if not files:
        print("Нет файлов логов для тестирования производительности.")
        return {}

    print("Проверка производительности".center(60))
    print(f"Files: {len(files)}")
    print(f"Threads: {settings.max_threads}   Processes: {settings.processes}")

    print("Прогрев кэша файловой системы...")
    warmup_cache(files)

    methods = [
        ("Sequential",      lambda: process_sequential(files)),
        ("Threads",         lambda: process_threads(files, settings.max_threads)),
        ("Asyncio",         lambda: process_asyncio(files, settings.max_threads)),
        ("Multiprocessing", lambda: process_multiprocessing(files, settings.processes)),
    ]
   
    random.shuffle(methods)

    results, counts = {}, {}
    for name, fn in methods:
        logger.info("Benchmark: %s — старт", name)
        t = time.perf_counter()
        try:
            res = fn()
        except Exception as exc:
            logger.exception("Benchmark %s упал: %s", name, exc)
            print(f"{name:>20}   ОШИБКА: {exc}")
            continue
        dur = time.perf_counter() - t
        results[name] = dur
        counts[name] = res["total"] if isinstance(res, dict) else int(res)
        logger.info("Benchmark: %s — %.2f сек (%d записей)",
                    name, dur, counts[name])

    if not results:
        print("Ни один метод не выполнился успешно.")
        return {}

    if len(set(counts.values())) != 1:
        logger.warning("Разное количество записей между методами: %s", counts)

    print(f"\nRecords: {max(counts.values())}")
    print()
    for name in sorted(results, key=results.get):
        print(f"{name:>20}: {results[name]:>7.2f} sec   ({counts[name]} записей)")

    fastest = min(results, key=results.get)
    print(f"\nFastest: {fastest}")
    logger.info("Результаты бенчмарка: %s", results)
    return results