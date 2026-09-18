import logging
from typing import List
import pandas as pd

logger = logging.getLogger(__name__)


class PandasAnalyzer:
    def __init__(self):
        self.df: pd.DataFrame = pd.DataFrame()

    def build(self, records: List[dict]) -> None:
        if not records:
            self.df = pd.DataFrame()
            return
        rows = []
        for r in records:
            rows.append({
                "date": r["date"],
                "server": r["server"],
                "level": r["level"],
                "message": r["message"],
            })
        self.df = pd.DataFrame(rows)

    def by_server(self) -> pd.DataFrame:
        if self.df.empty:
            return self.df
        g = self.df.groupby("server")
        agg = g.agg(
            total=("level", "size"),
            errors=("level", lambda s: (s == "ERROR").sum()),
            warnings=("level", lambda s: (s == "WARNING").sum()),
            critical=("level", lambda s: (s == "CRITICAL").sum()),
        ).reset_index()
        return agg.sort_values("errors", ascending=False)

    def by_level(self) -> pd.DataFrame:
        if self.df.empty:
            return self.df
        return (self.df.groupby("level").size()
                .reset_index(name="count")
                .sort_values("count", ascending=False))

    def by_date(self) -> pd.DataFrame:
        if self.df.empty:
            return self.df
        return (self.df.groupby("date").size()
                .reset_index(name="count")
                .sort_values("date"))

    def top_error_messages(self, n: int = 10) -> pd.DataFrame:
        if self.df.empty:
            return self.df
        errors = self.df[self.df["level"] == "ERROR"]
        return (errors.groupby("message").size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
                .head(n))