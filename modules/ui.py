import logging
from typing import Dict

from config import Settings
from modules.logs import LogManager
from modules.pipeline import build_pandas, save_all_reports
from modules.servers import ServerManager, compute_priority
from utils.display import header, table
from utils.helpers import (
    LogRecordIterator, format_error, format_record, severity_total, timer,
)

logger = logging.getLogger(__name__)


# Логи
def show_records(lm: LogManager, predicate, limit: int = 50,
                 mark_errors: bool = False) -> None:
    shown = 0
    for r in lm.iter_records():
        if predicate(r):
            if mark_errors and r["level"] in ("ERROR", "CRITICAL"):
                print(format_error(r))
            else:
                print(format_record("", r))
            shown += 1
            if shown >= limit:
                print(f"... (лимит {limit})")
                break


def browse_paginated(lm: LogManager, page_size: int = 20) -> None:
    it = LogRecordIterator(lm.iter_records(), page_size=page_size)
    page_no = 1
    while True:
        print(f"\n страница {page_no} (по {page_size}) ")
        got = 0
        try:
            for _ in range(page_size):
                r = next(it)
                print(format_record("", r))
                got += 1
        except StopIteration:
            print("(конец логов)")
            return
        if got == 0:
            print("(нет данных)")
            return
        if input("[Enter] далее | [q] выход: ").strip().lower() == "q":
            return
        page_no += 1


def menu_logs(lm: LogManager) -> None:
    while True:
        header("Логи")
        print("1) Все записи\n2) Только ERROR\n3) Только CRITICAL\n"
              "4) Только WARNING\n5) Поиск по сообщению\n6) Поиск по серверу\n"
              "7) Поиск по дате\n8) Постраничный просмотр\n0) Назад")
        c = input("> ").strip()
        if c == "0":
            return
        if c == "1":
            show_records(lm, lambda r: True)
        elif c == "2":
            show_records(lm, lambda r: r["level"] == "ERROR",
                         mark_errors=True)
        elif c == "3":
            show_records(lm, lambda r: r["level"] == "CRITICAL",
                         mark_errors=True)
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
        elif c == "8":
            try:
                ps = int(input("Размер страницы [20]: ") or 20)
            except ValueError:
                ps = 20
            browse_paginated(lm, ps)
        else:
            print("Неизвестная опция.")


# Сервера
def menu_servers(sm: ServerManager, lm: LogManager = None) -> None:
    while True:
        header("Серверы")
        print("1) Все серверы\n2) Активные серверы\n3) Проблемные серверы\n"
              "4) Поиск сервера\n5) Информация о сервере\n0) Назад")
        c = input("> ").strip()
        if c == "0":
            return
        if c == "1":
            table([[s.id, s.name, s.os, s.ip, s.cpu, s.ram, s.status]
                   for s in sm.all()],
                  headers=["ID", "Имя", "ОС", "IP", "CPU", "RAM", "Статус"])
        elif c == "2":
            table([[s.id, s.name, s.status] for s in sm.active()],
                  headers=["ID", "Имя", "Статус"])
        elif c == "3":
            if lm is None:
                print("LogManager недоступен.")
                continue
            _problem_servers_from_lm(lm)
        elif c == "4":
            q = input("Запрос: ").strip()
            for s in sm.find(q):
                print(f"{s.id}: {s.name} ({s.ip}) - {s.status}")
        elif c == "5":
            name = input("Имя сервера: ").strip()
            s = sm.get_by_name(name)
            if s:
                print(f"\nСервер {s.name}:")
                for k in ("id", "os", "ip", "environment", "cpu", "ram",
                          "status"):
                    print(f"  {k}: {getattr(s, k)}")
            else:
                print("Не найдено")


def _problem_servers_from_lm(lm: LogManager, top: int = 20) -> None:
    counts: Dict[str, Dict[str, int]] = {}
    with timer("Сканирование логов"):
        for r in lm.iter_records():
            s = r["server"]
            d = counts.setdefault(
                s, {"total": 0, "errors": 0, "critical": 0, "warnings": 0})
            d["total"] += 1
            lvl = r["level"]
            if lvl == "ERROR":
                d["errors"] += 1
            elif lvl == "CRITICAL":
                d["critical"] += 1
            elif lvl == "WARNING":
                d["warnings"] += 1

    rows = []
    for name, d in counts.items():
        pr = compute_priority(d["errors"], d["critical"],
                              d["warnings"], d["total"]).value
        score = d["critical"] * 3 + d["errors"] * 2 + d["warnings"]
        rows.append((score, name, d, pr))
    rows.sort(reverse=True)
    table([[name, d["errors"], d["critical"], d["warnings"], pr]
           for _, name, d, pr in rows[:top]],
          headers=["Сервер", "ERROR", "CRITICAL", "WARNING", "Приоритет"])


#  Статистика
def menu_statistics(analysis: dict, sm: ServerManager) -> None:
    pa = build_pandas(analysis)
    while True:
        header("Статистика")
        print("1) Общая\n2) По серверам\n3) По датам\n4) По уровням\n"
              "5) Нагрузка\n6) Аномалии\n"
              "7) Проблемные серверы (Pandas + приоритет)\n"
              "8) Топ-10 сообщений об ошибках\n9) Сводка по часам\n"
              "10) Сводные метрики (describe)\n0) Назад")
        c = input("> ").strip()
        if c == "0":
            return

        if c == "1":
            print(f"Всего серверов: {len(sm.all())}")
            print(f"Активных: {len(sm.active())}")
            print(f"Всего записей: {analysis['total_records']}")
            for k, v in analysis["level_counts"].items():
                print(f"  {k}: {v}")
            print(f"Суммарный 'вес' серьёзности: "
                  f"{severity_total(analysis['level_counts'])}")
        elif c == "2":
            df = pa.by_server(top=50)
            table(df.values.tolist(),
                  headers=[c_.replace("_", " ").title() for c_ in df.columns])
        elif c == "3":
            df = pa.by_date()
            table(df.values.tolist(), headers=["Дата", "Записей"])
        elif c == "4":
            df = pa.by_level()
            table(df.values.tolist(), headers=["Уровень", "Записей"])
        elif c == "5":
            if not analysis["numeric"]:
                print("(нет числовых метрик)")
            else:
                for k, s in analysis["numeric"].items():
                    print(f"{k.upper():<5} среднее={s['mean']:.2f} "
                          f"мин={s['min']:.0f} макс={s['max']:.0f} "
                          f"медиана={s['median']:.2f} "
                          f"ст.отклон={s['std']:.2f}")
        elif c == "6":
            print(f"Аномалий: {len(analysis['anomalies'])}")
            for a in analysis["anomalies"][:30]:
                print(f"  {a['timestamp']} | {a['server']:>12} | "
                      f"{a['metric']:<5} = {a['value']:>6} | "
                      f"z={a['z_score']}")
        elif c == "7":
            df = pa.problem_servers(top=20)
            if df.empty:
                print("(нет данных)")
            else:
                table(df.values.tolist(),
                      headers=[c_.replace("_", " ").title()
                               for c_ in df.columns])
        elif c == "8":
            df = pa.top_error_messages(10)
            table(df.values.tolist(), headers=["Сообщение", "Кол-во"])
        elif c == "9":
            df = pa.by_time_period()
            rows = [[f"{h}:00-{int(h) + 1:02d}:00", n]
                    for h, n in df.values.tolist()]
            table(rows, headers=["Период", "Записей"])
        elif c == "10":
            d = pa.describe()
            if not d:
                print("(нет данных)")
            else:
                for stat, vals in d.items():
                    print(f"  {stat}: {vals}")
        else:
            print("Неизвестная опция.")


#  Репорты
def menu_reports(analysis: dict, sm: ServerManager,
                 settings: Settings = None) -> None:
    header("Отчёты")
    print("1) Сохранить все отчеты\n0) Назад")
    if input("> ").strip() != "1":
        return
    if settings is None:
        print("Настройки не заданы")
        return
    save_all_reports(analysis, sm, settings)
    print("Отчеты сохранены.")


# Настройка
def _ask_int(prompt: str, current: int, min_val: int = 1) -> int:
    raw = input(f"{prompt} [{current}]: ").strip()
    if not raw:
        return current
    v = int(raw)
    if v < min_val:
        raise ValueError(f"{prompt} должно быть >= {min_val}")
    return v


def _ask_float(prompt: str, current: float, min_val: float = 0.1) -> float:
    raw = input(f"{prompt} [{current}]: ").strip()
    if not raw:
        return current
    v = float(raw)
    if v < min_val:
        raise ValueError(f"{prompt} должно быть >= {min_val}")
    return v


def menu_settings(settings: Settings) -> None:
    header("Настройки")
    for name in ("max_threads", "processes", "anomaly_threshold",
                 "test_servers", "test_logs",
                 "logs_path", "data_path", "reports_path"):
        print(f"  {name}: {getattr(settings, name)}")

    if input("Изменить? (y/n): ").strip().lower() != "y":
        return
    try:
        settings.max_threads = _ask_int(
            "Макс. потоков", settings.max_threads, 1)
        settings.processes = _ask_int(
            "Процессов", settings.processes, 1)
        settings.anomaly_threshold = _ask_float(
            "Порог аномалий", settings.anomaly_threshold, 0.1)
        settings.test_servers = _ask_int(
            "Тест. серверов", settings.test_servers, 1)
        settings.test_logs = _ask_int(
            "Тест. логов", settings.test_logs, 1)
        for field, label in (("logs_path", "логам"),
                             ("data_path", "данным"),
                             ("reports_path", "отчётам")):
            v = input(f"Путь к {label} "
                      f"[{getattr(settings, field)}]: ").strip()
            if v:
                setattr(settings, field, v)
        settings.save()
        print("Сохранено.")
    except ValueError as exc:
        print(f"Неверный ввод: {exc}. Не сохранено.")