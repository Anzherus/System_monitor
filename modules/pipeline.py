import logging
from collections import Counter
from typing import Dict, List

import pandas as pd

from config import Settings
from modules.analyzer import (
    AnomalyDetector,
    NumericAnalyzer,
    PerServerNumericAnalyzer,
)
from modules.logs import LogManager
from modules.reports import ReportGenerator
from modules.servers import ServerManager
from modules.statistics import PandasAnalyzer
from utils.helpers import detect_floods, timer

logger = logging.getLogger(__name__)

MAX_ERROR_RECORDS_FOR_FLOOD = 200_000


def run_analysis(sm: ServerManager, lm: LogManager,settings: Settings = None) -> dict:
    logger.info("Начало анализа")
    num = NumericAnalyzer()
    psn = PerServerNumericAnalyzer()
    threshold = settings.anomaly_threshold if settings else 2.0
    det = AnomalyDetector(threshold=threshold)

    level_counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    total = 0
    per_server: Dict[str, Dict[str, int]] = {}
    per_date: Dict[str, int] = {}
    per_hour: Dict[str, int] = {}
    error_messages: Counter = Counter()
    error_records: List[dict] = []

    with timer("Анализ логов"):
        for r in lm.iter_records():
            total += 1
            lvl = r["level"]
            level_counts[lvl] = level_counts.get(lvl, 0) + 1
            num.feed(r)
            psn.feed(r)
            det.feed(r)

            srv = r["server"]
            d = per_server.setdefault(
                srv, {"total": 0, "errors": 0, "critical": 0, "warnings": 0})
            d["total"] += 1
            if lvl == "ERROR":
                d["errors"] += 1
                error_messages[r["message"]] += 1
                if len(error_records) < MAX_ERROR_RECORDS_FOR_FLOOD:
                    error_records.append(r)
            elif lvl == "CRITICAL":
                d["critical"] += 1
                if len(error_records) < MAX_ERROR_RECORDS_FOR_FLOOD:
                    error_records.append(r)
            elif lvl == "WARNING":
                d["warnings"] += 1

            per_date[r["date"]] = per_date.get(r["date"], 0) + 1
            hour = r["time"][:2]
            per_hour[hour] = per_hour.get(hour, 0) + 1

    anomalies = det.result()
    numeric = num.result()
    per_server_numeric = psn.per_server()

    sorted_for_flood = sorted(
        error_records, key=lambda r: (r["server"], r["message"]))
    floods = list(detect_floods(sorted_for_flood, min_run=3))
    logger.info("Обработано %d записей, аномалий: %d, флудов: %d",
                total, len(anomalies), len(floods))

    print("\nУровни логирования")
    for k, v in level_counts.items():
        print(f"  {k}: {v}")

    print("\nНагрузка")
    if numeric:
        for k, stats in numeric.items():
            print(f"  {k.upper():<5} среднее={stats['mean']:.2f} "
                  f"мин={stats['min']:.0f} макс={stats['max']:.0f} "
                  f"медиана={stats['median']:.2f} "
                  f"ст.отклон={stats['std']:.2f}")
    else:
        print("  (нет числовых метрик)")

    print(f"\nАномалий обнаружено: {len(anomalies)}")
    logger.info("Анализ завершён")

    return {
        "total_records":      total,
        "level_counts":       level_counts,
        "numeric":            numeric,
        "per_server_numeric": per_server_numeric,
        "anomalies":          anomalies,
        "per_server":         per_server,
        "per_date":           per_date,
        "per_hour":           per_hour,
        "top_error_messages": sorted(error_messages.items(),key=lambda kv: -kv[1])[:10],
        "error_records":      error_records,
        "floods":             floods,
        "anomaly_stats":      det.summary() if hasattr(det, "summary")
                              else det.stats_summary(),
    }


def build_pandas(analysis: dict) -> PandasAnalyzer:
    pa = PandasAnalyzer()
    pa.build(
        per_server=analysis["per_server"],
        level_counts=analysis["level_counts"],
        per_date=analysis["per_date"],
        per_hour=analysis["per_hour"],
        error_messages=dict(analysis["top_error_messages"]),
        per_server_numeric=analysis.get("per_server_numeric"),
    )
    return pa


def _is_valid_float(v) -> bool:
    return v is not None and not (isinstance(v, float) and pd.isna(v))


def build_text_report(analysis: dict, sm: ServerManager,
                      problem_df) -> str:
    lines = ["Отчёт System Monitor".center(60)]
    lines.append("\nОбщая информация")
    lines.append(f"  Всего серверов:   {len(sm.all())}")
    lines.append(f"  Активных:         {len(sm.active())}")
    lines.append(f"  Всего записей:    {analysis['total_records']}")

    lines.append("\nУровни")
    for lvl, n in analysis["level_counts"].items():
        lines.append(f"  {lvl}: {n}")

    lines.append("\nНагрузка")
    if analysis["numeric"]:
        for m, s in analysis["numeric"].items():
            lines.append(f"  {m.upper():<5} среднее={s['mean']:.2f} "
                         f"мин={s['min']:.0f} макс={s['max']:.0f} "
                         f"медиана={s['median']:.2f} "
                         f"ст.отклон={s['std']:.2f}")
    else:
        lines.append("  (нет данных)")

    lines.append(f"\nАномалий: {len(analysis['anomalies'])}")
    if analysis["anomalies"]:
        lines.append("\nТОП-10 Адномалий")
        top = sorted(analysis["anomalies"],
                     key=lambda a: a["z_score"], reverse=True)[:10]
        for a in top:
            lines.append(f"  {a['timestamp']} | {a['server']:<14} | "
                         f"{a['metric']:<5} = {a['value']:>6} | "
                         f"z={a['z_score']}")

    if problem_df is not None and not problem_df.empty:
        lines.append("\nПроблемные сервера(топ-10)")
        has_cpu = "avg_cpu" in problem_df.columns
        for _, row in problem_df.head(10).iterrows():
            extra = ""
            if has_cpu and _is_valid_float(row.get("avg_cpu")):
                extra = f" avg_cpu={row['avg_cpu']:.1f}"
            lines.append(
                f"  {row['server']:<14} ERROR={int(row['errors']):<6} "
                f"CRITICAL={int(row['critical']):<5} "
                f"WARNING={int(row['warnings']):<6} "
                f"PRIORITY={row['priority']}{extra}")

    floods = analysis.get("floods") or []
    if floods:
        lines.append("\nВсплески одинаковых сообщений(itertools.groupby)")
        for f in sorted(floods, key=lambda x: -x["count"])[:10]:
            lines.append(f"  {f['server']:<14} ×{f['count']:<5} "
                         f"{f['message'][:60]}")
    return "\n".join(lines)


def save_all_reports(analysis: dict, sm: ServerManager,
                     settings: Settings) -> None:
    rg = ReportGenerator(settings)
    pa = build_pandas(analysis)

    status_counts = {"active": 0, "inactive": 0,
                     "maintenance": 0, "unavailable": 0}
    for s in sm.all():
        status_counts[s.status] = status_counts.get(s.status, 0) + 1

    problem_df = pa.problem_servers(top=10)
    servers_df = pa.by_server()
    stats_df = pa.by_level()

    top_anomalies = sorted(analysis["anomalies"],
                           key=lambda a: a["z_score"], reverse=True)[:10]

    summary = {
        "total_servers":       len(sm.all()),
        "active_servers":      status_counts.get("active", 0),
        "inactive_servers":    status_counts.get("inactive", 0),
        "maintenance_servers": status_counts.get("maintenance", 0),
        "unavailable_servers": status_counts.get("unavailable", 0),
        "total_records":       analysis["total_records"],
        "levels":              analysis["level_counts"],
        "load":                analysis["numeric"],
        "per_server_load":     analysis.get("per_server_numeric", {}),
        "anomalies_count":     len(analysis["anomalies"]),
        "top_anomalies":       top_anomalies,
        "problem_servers":     problem_df.to_dict(orient="records")
                               if not problem_df.empty else [],
        "floods":              analysis.get("floods", [])[:50],
        "anomaly_stats":       analysis.get("anomaly_stats", {}),
    }

    rg.save_summary(summary)
    rg.save_errors(analysis["error_records"])
    rg.save_anomalies(analysis["anomalies"])
    if not servers_df.empty:
        rg.save_servers_csv(servers_df)
    if not stats_df.empty:
        rg.save_statistics_csv(stats_df)
    if not problem_df.empty:
        rg.save_problem_servers_csv(problem_df)
    rg.save_text_report(build_text_report(analysis, sm, problem_df))