import logging, time
from config import Settings
from modules.logs import LogManager
from modules.parallel import process_asyncio, process_multiprocessing, process_sequential, process_threads

logger = logging.getLogger(__name__)


def run_benchmark(settings: Settings) -> dict:
    files = LogManager(settings.logs_path).files()
    if not files:
        print("Нет файлов логов для тестирования производительности.")
        return {}
    print("ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ".center(60))
    print(f"Файлы: {len(files)}")

    results = {}

    t = time.perf_counter()
    total_seq = process_sequential(files)
    results["Последовательный"] = time.perf_counter() - t

    t = time.perf_counter()
    total_thr = process_threads(files, settings.max_threads)
    results["Многопоточный"] = time.perf_counter() - t

    t = time.perf_counter()
    total_asyn = process_asyncio(files)
    results["Asyncio"] = time.perf_counter() - t

    t = time.perf_counter()
    mp_res = process_multiprocessing(files, settings.processes)
    results["Многопроцессный"] = time.perf_counter() - t

    print(f"\nЗаписи: {total_seq}")
    for name, dur in results.items():
        print(f"{name:>20} {dur:>8.2f} сек")

    fastest = min(results, key=results.get)
    print(f"\nСамый быстрый: {fastest}")
    logger.info("Результаты бенчмарка: %s", results)
    return results