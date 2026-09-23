"""
анализ агрегатов.
"""
import logging
from typing import Iterable, Optional

import pandas as pd

from modules.servers import compute_priority

logger = logging.getLogger(__name__)

# Метрики, по которым имеет смысл считать avg_* в сводных таблицах
NUMERIC_METRICS = ("cpu", "ram", "disk", "net")


class PandasAnalyzer:

    def __init__(self):
        self.servers_df = pd.DataFrame()
        self.levels_df = pd.DataFrame()
        self.dates_df = pd.DataFrame()
        self.hours_df = pd.DataFrame()
        self.errors_df = pd.DataFrame()

    def build(self, per_server, level_counts, per_date, per_hour, error_messages, per_server_numeric=None):
        self.servers_df = pd.DataFrame(
            [{"server": s, **d} for s, d in per_server.items()]
        ) if per_server else pd.DataFrame(
            columns=["server", "total", "errors", "critical", "warnings"])

        if per_server_numeric and not self.servers_df.empty:
            for metric in NUMERIC_METRICS:
                col = f"avg_{metric}"
                mapping = {}
                for srv, stats in per_server_numeric.items():
                    mean_val = stats.get(metric, {}).get("mean")
                    if mean_val is not None:
                        mapping[srv] = mean_val
                
                if mapping:
                    series = self.servers_df["server"].map(mapping)
                    self.servers_df[col] = series
                else:
                    self.servers_df[col] = None

        self.levels_df = pd.DataFrame(
            [{"level": k, "count": v} for k, v in level_counts.items()]
        )
        self.dates_df = pd.DataFrame(
            [{"date": k, "count": v} for k, v in per_date.items()]
        )
        self.hours_df = pd.DataFrame(
            [{"hour": k, "count": v} for k, v in per_hour.items()]
        )
        self.errors_df = pd.DataFrame(
            [{"message": m, "count": c} for m, c in error_messages.items()]
        )

    @classmethod
    def from_records(cls, records):
        per_server, level_counts = {}, {}
        per_date, per_hour = {}, {}
        errors = {}
        per_server_numeric = {}
        
        from modules.analyzer import PerServerNumericAnalyzer
        psn = PerServerNumericAnalyzer()
        
        for r in records:
            srv = r["server"]
            d = per_server.setdefault(
                srv, {"total": 0, "errors": 0, "critical": 0, "warnings": 0})
            d["total"] += 1
            lvl = r["level"]
            level_counts[lvl] = level_counts.get(lvl, 0) + 1
            if lvl == "ERROR":
                d["errors"] += 1
                errors[r["message"]] = errors.get(r["message"], 0) + 1
            elif lvl == "CRITICAL":
                d["critical"] += 1
            elif lvl == "WARNING":
                d["warnings"] += 1
            per_date[r["date"]] = per_date.get(r["date"], 0) + 1
            hour = r["time"][:2]
            per_hour[hour] = per_hour.get(hour, 0) + 1
            # Также фидим числовые метрики
            psn.feed(r)
        
        pa = cls()
        per_server_numeric_data = psn.per_server()
        pa.build(per_server, level_counts, per_date, per_hour, errors, per_server_numeric_data)
        return pa

    # группировка/сортировка
    def by_server(self, top: Optional[int] = None):
        if self.servers_df.empty:
            return self.servers_df
        df = (self.servers_df
              .sort_values(["errors", "critical"], ascending=False)
              .reset_index(drop=True))
        return df.head(top) if top else df

    def by_level(self):
        if self.levels_df.empty:
            return self.levels_df
        return (self.levels_df
                .sort_values("count", ascending=False)
                .reset_index(drop=True))

    def by_date(self):
        return self.dates_df.sort_values("date").reset_index(drop=True)

    def by_time_period(self):
        return self.hours_df.sort_values("hour").reset_index(drop=True)

    def top_error_messages(self, n: int = 10):
        if self.errors_df.empty:
            return self.errors_df
        return (self.errors_df
                .sort_values("count", ascending=False)
                .head(n)
                .reset_index(drop=True))

    # фильтрация
    def filter_min_errors(self, threshold: int = 1):
        if self.servers_df.empty:
            return self.servers_df
        # errors существует
        if "errors" not in self.servers_df.columns:
            return pd.DataFrame(columns=self.servers_df.columns)
        return self.servers_df[self.servers_df["errors"] >= threshold]

    # статистика и приоритеты
    def problem_servers(self, top: int = 10):
        if self.servers_df.empty:
            return self.servers_df
        df = self.servers_df.copy()
        df["score"] = df["critical"] * 3 + df["errors"] * 2 + df["warnings"]
        df["priority"] = df.apply(
            lambda r: compute_priority(int(r["errors"]), int(r["critical"]),
                                       int(r["warnings"]), int(r["total"])).value,
            axis=1,
        )
        return (df.sort_values(["score", "critical"], ascending=False)
                  .drop(columns="score")
                  .head(top)
                  .reset_index(drop=True))

    def describe(self):
        if self.servers_df.empty:
            return {}
        cols = [c for c in ("total", "errors", "critical", "warnings")
                if c in self.servers_df.columns]
        if not cols:
            return {}
        numeric = self.servers_df[cols]
        return {
            "mean": numeric.mean().round(2).to_dict(),
            "median": numeric.median().round(2).to_dict(),
            "std": numeric.std().round(2).to_dict(),
            "max": numeric.max().to_dict(),
        }