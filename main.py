"""
Главный файл System Monitor.
"""
import asyncio
import glob
import logging
import os
import sys

from config import Settings, ensure_dirs
from modules.servers import ServerManager
from modules.logs import LogManager
from modules.benchmark import run_benchmark
from modules.generator import generate_infrastructure
from modules.final_test import run_final_test
from modules.pipeline import run_analysis
from modules.ui import (
    menu_servers, menu_logs, menu_settings,
    menu_statistics, menu_reports,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("system_monitor")

settings = Settings.load()
ensure_dirs(settings)

_file_handler = None


def setup_file_handler(s: Settings) -> None:
    """Перевешивает FileHandler на актуальный logs_path."""
    global _file_handler
    if _file_handler is not None:
        logging.getLogger().removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None
    os.makedirs(s.logs_path, exist_ok=True)
    h = logging.FileHandler(os.path.join(s.logs_path, "application.log"),
                            encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(h)
    _file_handler = h


setup_file_handler(settings)



def _quick_scan(path: str) -> dict:
    """Быстрый проход по одному файлу: счётчики по уровням."""
    from modules.parser import iter_log_file
    counts = {"total": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    for rec in iter_log_file(path):
        counts["total"] += 1
        lvl = rec["level"]
        counts[lvl] = counts.get(lvl, 0) + 1
    return counts


async def _watch_loop(logs_path: str, interval: float) -> None:
    """Периодически проверяет появление новых лог-файлов."""
    pattern = os.path.join(logs_path, "*.log")
    seen = set(glob.glob(pattern))
    logger.info("Watch: исходно видно %d файлов", len(seen))
    while True:
        await asyncio.sleep(interval)
        current = set(glob.glob(pattern))
        new_files = current - seen
        if not new_files:
            continue
        logger.info("Watch: обнаружено %d новых файлов", len(new_files))
        for path in sorted(new_files):
            loop = asyncio.get_running_loop()
            counts = await loop.run_in_executor(None, _quick_scan, path)
            print(f"  {os.path.basename(path)}: {counts}")
        seen = current


def watch_mode(settings: Settings, interval: float = 5.0) -> None:
    print(f"\nНаблюдение за {settings.logs_path} (Ctrl+C — выход).")
    logger.info("Watch mode старт (интервал %.1f сек)", interval)
    try:
        asyncio.run(_watch_loop(settings.logs_path, interval))
    except KeyboardInterrupt:
        pass
    logger.info("Watch mode остановлен")
    print("\nНаблюдение остановлено.")



def main() -> None:
    logger.info("Приложение запущено")

    sm = ServerManager(settings)
    lm = LogManager(settings.logs_path)
    sm.load()

    state = {"analysis": None}

    while True:
        print("System monitor".center(60))
        print("1.  Серверы")
        print("2.  Логи")
        print("3.  Анализ")
        print("4.  Статистика")
        print("5.  Аномалии")
        print("6.  Отчеты")
        print("7.  Генерация тестовых данных")
        print("8.  Бенчмарк производительности")
        print("9.  Настройки")
        print("10. Режим наблюдения (watch)")
        print("11. Финальный тест (100 серверов / 500 файлов / 1M)")
        print("0.  Выход")

        try:
            choice = input("\n> ").strip()
        except EOFError:
            choice = "0"

        if choice == "0":
            logger.info("Приложение завершено")
            print("\nДо свидания!")
            return
        elif choice == "1":
            menu_servers(sm, lm)
        elif choice == "2":
            menu_logs(lm)
        elif choice == "3":
            try:
                state["analysis"] = run_analysis(sm, lm, settings)
            except Exception as exc:
                logger.exception("Ошибка анализа")
                print(f"Ошибка анализа: {exc}")
        elif choice == "4":
            if state["analysis"] is None:
                print("\nСначала выполните Анализ (пункт 3).")
            else:
                menu_statistics(state["analysis"], sm)
        elif choice == "5":
            if state["analysis"] is None:
                print("\nСначала выполните Анализ (пункт 3).")
            else:
                anomalies = state["analysis"]["anomalies"]
                print(f"\nАномалий обнаружено: {len(anomalies)}")
                for i, a in enumerate(anomalies[:30], 1):
                    print(f"{i}. {a['timestamp']} | {a['server']} | "
                          f"{a['metric']} = {a['value']} "
                          f"(z={a['z_score']})")
        elif choice == "6":
            if state["analysis"] is None:
                print("\nСначала выполните Анализ (пункт 3).")
            else:
                menu_reports(state["analysis"], sm, settings)
        elif choice == "7":
            try:
                n_srv = int(input(f"\nСерверов [{settings.test_servers}]: ")
                          or settings.test_servers)
                n_log = int(input(f"Логов [{settings.test_logs}]: ")
                          or settings.test_logs)
                n_files = int(input("Файлов [auto]: ") or 0)
                if n_srv < 1 or n_log < 1:
                    raise ValueError("числа должны быть >= 1")
                generate_infrastructure(settings, n_srv, n_log,
                                        n_files or None)
                sm.load()
                state["analysis"] = None
                print("\nТестовые данные сгенерированы.")
            except ValueError as exc:
                print(f"\nНеверное число: {exc}")
        elif choice == "8":
            try:
                run_benchmark(settings)
            except Exception as exc:
                logger.exception("Ошибка бенчмарка")
                print(f"Ошибка бенчмарка: {exc}")
        elif choice == "9":
            old_logs = settings.logs_path
            old_data = settings.data_path
            menu_settings(settings)
            changed = False
            if settings.logs_path != old_logs:
                ensure_dirs(settings)
                setup_file_handler(settings)
                lm = LogManager(settings.logs_path)
                changed = True
                logger.info("Путь логов изменён на %s", settings.logs_path)
            if settings.data_path != old_data:
                ensure_dirs(settings)
                sm = ServerManager(settings)
                sm.load()
                changed = True
                logger.info("Путь данных изменён на %s", settings.data_path)
            if changed:
                state["analysis"] = None
        elif choice == "10":
            try:
                watch_mode(settings)
            except Exception as exc:
                logger.exception("Ошибка режима наблюдения")
                print(f"Ошибка: {exc}")
        elif choice == "11":
            try:
                n_srv = int(input("\nСерверов [100]: ") or 100)
                n_files = int(input("Файлов [500]: ") or 500)
                n_recs = int(input("Записей [1000000]: ") or 1_000_000)
                if min(n_srv, n_files, n_recs) < 1:
                    raise ValueError("числа должны быть >= 1")
                run_final_test(settings, n_srv, n_files, n_recs)
                sm.load()
                state["analysis"] = None
            except ValueError as exc:
                print(f"\nНеверное число: {exc}")
            except Exception as exc:
                logger.exception("Ошибка финального теста")
                print(f"Ошибка: {exc}")
        else:
            print("\nНеизвестная опция.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nПрограмма прервана пользователем.")
        logger.info("Программа прервана пользователем")
    except Exception as e:
        logger.exception("Критическая ошибка")
        print(f"\nПроизошла ошибка: {e}")
        sys.exit(1)