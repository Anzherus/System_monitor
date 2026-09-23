import logging, time

from config import Settings
from modules.generator import generate_infrastructure
from modules.logs import LogManager
from modules.pipeline import run_analysis, save_all_reports
from modules.servers import ServerManager

logger = logging.getLogger(__name__)


def run_final_test(settings: Settings, servers_count: int = 100, files_count: int = 500, records_count: int = 1_000_000):
    print("Финальный тест".center(60))
    print(f"Серверов: {servers_count}")
    print(f"Файлов:   {files_count}")
    print(f"Записей: {records_count}")

    timings = {}

    logger.info("Финальный тест: генерация %d записей в %d файлах", records_count, files_count)
    t0 = time.perf_counter()
    generate_infrastructure(settings, servers_count, records_count, files_count)
    timings["generate"] = time.perf_counter() - t0
    print(f"1. Генерация данных:  {timings['generate']:>7.2f} сек")

    logger.info("Финальный тест: загрузка серверов")
    t0 = time.perf_counter()
    sm = ServerManager(settings)
    sm.load()
    timings["load"] = time.perf_counter() - t0
    print(f"2. Загрузка серверов: {timings['load']:>7.2f} сек "
          f"({len(sm.all())} шт.)")

    lm = LogManager(settings.logs_path)
    logger.info("Финальный тест: анализ")
    t0 = time.perf_counter()
    analysis = run_analysis(sm, lm, settings)
    timings["analyze"] = time.perf_counter() - t0
    print(f"3-6. Анализ:          {timings['analyze']:>7.2f} сек "
          f"({analysis['total_records']} записей, "
          f"{len(analysis['anomalies'])} аномалий)")

    logger.info("Финальный тест: сохранение отчётов")
    t0 = time.perf_counter()
    save_all_reports(analysis, sm, settings)
    timings["reports"] = time.perf_counter() - t0
    print(f"7-8. Отчёты:          {timings['reports']:>7.2f} сек")

    total = sum(timings.values())
    print(f"\nИТОГО: {total:.2f} сек")
    print(f"Записей обработано: {analysis['total_records']}")
    print(f"Аномалий найдено:   {len(analysis['anomalies'])}")
    logger.info("Финальный тест завершён за %.2f сек", total)
    return timings