"""Модуль пользовательского интерфейса для System Monitor"""
import logging
from typing import List
from config import Settings
from modules.servers import ServerManager
from modules.logs import LogManager
from modules.analyzer import NumericAnalyzer, AnomalyDetector
from modules.reports import ReportGenerator
from modules.statistics import PandasAnalyzer
from utils.display import header, table
from utils.helpers import timer

logger = logging.getLogger(__name__)


def show_records(lm: LogManager, predicate, limit: int = 50) -> None:
    """Показать записи логов с фильтрацией"""
    shown = 0
    for r in lm.iter_records():
        if predicate(r):
            print(f"{r['date']} {r['time']} | {r['server']:>10} | {r['level']:<8} | {r['message']}")
            shown += 1
            if shown >= limit:
                print(f"... (лимит {limit})")
                break


def menu_servers(sm: ServerManager) -> None:
    """Меню управления серверами"""
    while True:
        header("СЕРВЕРЫ")
        print("1) Все серверы\n2) Активные серверы\n3) Проблемные серверы\n4) Поиск сервера\n5) Информация о сервере\n0) Назад")
        c = input("> ").strip()
        if c == "0":
            return
        elif c == "1":
            table([[s.id, s.name, s.os, s.ip, s.cpu, s.ram, s.status]
                   for s in sm.all()],
                  headers=["ID", "Имя", "ОС", "IP", "CPU", "RAM", "Статус"])
        elif c == "2":
            table([[s.id, s.name, s.status] for s in sm.active()],
                  headers=["ID", "Имя", "Статус"])
        elif c == "3":
            print("Проблемные серверы рассчитываются после Анализа (Статистика -> по серверам).")
        elif c == "4":
            q = input("Запрос: ").strip()
            for s in sm.find(q):
                print(f"{s.id}: {s.name} ({s.ip}) - {s.status}")
        elif c == "5":
            name = input("Имя сервера: ").strip()
            s = sm.get_by_name(name)
            if s:
                print(f"\nСервер {s.name}:")
                print(f"  ID: {s.id}")
                print(f"  ОС: {s.os}")
                print(f"  IP: {s.ip}")
                print(f"  Окружение: {s.environment}")
                print(f"  CPU: {s.cpu}")
                print(f"  RAM: {s.ram}")
                print(f"  Статус: {s.status}")
            else:
                print("Не найдено")


def menu_logs(lm: LogManager) -> None:
    """Меню работы с логами"""
    while True:
        header("ЛОГИ")
        print("1) Все записи\n2) Только ERROR\n3) Только CRITICAL\n4) Только WARNING\n"
              "5) Поиск по сообщению\n6) Поиск по серверу\n7) Поиск по дате\n0) Назад")
        c = input("> ").strip()
        if c == "0":
            return
        if c == "1":
            show_records(lm, lambda r: True)
        elif c == "2":
            show_records(lm, lambda r: r["level"] == "ERROR")
        elif c == "3":
            show_records(lm, lambda r: r["level"] == "CRITICAL")
        elif c == "4":
            show_records(lm, lambda r: r["level"] == "WARNING")
        elif c == "5":
            q = input("Подстрока: ").lower()
            show_records(lm, lambda r: q in r["message"].lower())
        elif c == "6":
            q = input("Сервер: ").strip()
            show_records(lm, lambda r: r["server"] == q)
        elif c == "7":
            q = input("Дата (ГГГГ-ММ-ДД): ").strip()
            show_records(lm, lambda r: r["date"] == q)
        else:
            print("Неизвестная опция.")


def run_analysis(sm: ServerManager, lm: LogManager, settings: Settings = None):
    """Запустить анализ данных"""
    logger.info("Начало анализа")
    num = NumericAnalyzer()
    threshold = settings.anomaly_threshold if settings else 3.0
    det = AnomalyDetector(threshold)
    records = []
    level_counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    
    with timer("Последовательный парсинг"):
        for r in lm.iter_records():
            records.append(r)
            level_counts[r["level"]] = level_counts.get(r["level"], 0) + 1
            num.feed(r)
            det.feed(r)
    
    numeric = num.result()
    anomalies = det.detect()
    logger.info("Обработано %d записей", len(records))
    logger.info("Найдено %d аномалий", len(anomalies))
    
    print("\nУРОВНИ ЛОГИРОВАНИЯ")
    for k, v in level_counts.items():
        print(f"{k}: {v}")
    
    print("\nНАГРУЗКА (NumPy)")
    for k, stats in numeric.items():
        print(f"{k.upper():<5} среднее={stats['mean']:.2f} мин={stats['min']:.0f} макс={stats['max']:.0f} "
              f"медиана={stats['median']:.2f} ст.отклон={stats['std']:.2f}")
    
    print(f"\nАномалий обнаружено: {len(anomalies)}")
    
    logger.info("Анализ завершен")
    return records, numeric, anomalies


def menu_statistics(records, numeric, anomalies, sm: ServerManager) -> None:
    """Меню статистики"""
    header("СТАТИСТИКА")
    print("1) Общая\n2) По серверам\n3) По датам\n4) По уровням\n5) Нагрузка\n6) Аномалии\n0) Назад")
    c = input("> ").strip()
    if c == "0":
        return
    
    pa = PandasAnalyzer()
    pa.build(records)
    
    if c == "1":
        total = len(records)
        print(f"Всего серверов: {len(sm.all())}")
        print(f"Активных: {len(sm.active())}")
        print(f"Всего записей: {total}")
        for k in ("INFO", "WARNING", "ERROR", "CRITICAL"):
            n = sum(1 for r in records if r["level"] == k)
            print(f"{k}: {n}")
    elif c == "2":
        df = pa.by_server()
        print(df.to_string(index=False) if not df.empty else "(нет данных)")
    elif c == "3":
        df = pa.by_date()
        print(df.to_string(index=False) if not df.empty else "(нет данных)")
    elif c == "4":
        df = pa.by_level()
        print(df.to_string(index=False) if not df.empty else "(нет данных)")
    elif c == "5":
        for k, s in numeric.items():
            print(f"{k.upper():<5} среднее={s['mean']:.2f} ст.отклон={s['std']:.2f}")
    elif c == "6":
        print(f"Аномалий: {len(anomalies)}")
        for a in anomalies[:20]:
            print(f"Сервер: {a['server']}, Метрика: {a['metric']}, "
                  f"Значение: {a['value']}, Z-оценка: {a['z_score']}")


def _build_text_report(summary: dict, anomalies) -> str:
    """Создать текстовый отчет"""
    lines = ["ОТЧЕТ SYSTEM MONITOR".center(60)]
    lines.append("\nОБЩАЯ ИНФОРМАЦИЯ")
    for k, v in summary.items():
        if k != "load":
            lines.append(f"  {k}: {v}")
    lines.append("\nНАГРУЗКА")
    for m, s in summary.get('load', {}).items():
        lines.append(f"  {m.upper():<5} среднее={s['mean']:.2f} мин={s['min']:.0f} "
                     f"макс={s['max']:.0f} ст.отклон={s['std']:.2f}")
    lines.append(f"\nАНОМАЛИЙ: {len(anomalies)}")
    return "\n".join(lines)


def menu_reports(records, numeric, anomalies, sm: ServerManager, settings: Settings = None) -> None:
    """Меню отчетов"""
    header("ОТЧЕТЫ")
    print("1) Сохранить все отчеты\n0) Назад")
    c = input("> ").strip()
    if c != "1":
        return
    
    if settings is None:
        print("Настройки не заданы")
        return
    rg = ReportGenerator(settings)
    summary = {
        "total_servers": len(sm.all()),
        "active_servers": len(sm.active()),
        "total_records": len(records),
        "levels": {k: sum(1 for r in records if r["level"] == k) 
                  for k in ("INFO", "WARNING", "ERROR", "CRITICAL")},
        "load": numeric,
        "anomalies_count": len(anomalies),
    }
    
    rg.save_summary(summary)
    rg.save_errors([r for r in records if r["level"] == "ERROR"])
    
    pa = PandasAnalyzer()
    pa.build(records)
    if not pa.df.empty:
        rg.save_servers_csv(pa.by_server())
        rg.save_statistics_csv(pa.by_level())
    
    rg.save_text_report(_build_text_report(summary, anomalies))
    print("Отчеты сохранены.")


def menu_settings(settings) -> None:
    """Меню настроек"""
    header("НАСТРОЙКИ")
    print(f"Макс. потоков: {settings.max_threads}")
    print(f"Процессов: {settings.processes}")
    print(f"Порог аномалий: {settings.anomaly_threshold}")
    print(f"Тест. серверов: {settings.test_servers}")
    print(f"Тест. логов: {settings.test_logs}")
    
    if input("Изменить? (y/n): ").strip().lower() == "y":
        try:
            settings.max_threads = int(input("Макс. потоков: "))
            settings.processes = int(input("Процессов: "))
            settings.anomaly_threshold = float(input("Порог аномалий: "))
            settings.test_servers = int(input("Тест. серверов: "))
            settings.test_logs = int(input("Тест. логов: "))
            settings.save()
            print("Сохранено.")
        except ValueError:
            print("Неверный ввод. Не сохранено.")