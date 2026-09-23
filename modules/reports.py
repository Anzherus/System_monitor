import json
import logging
import math
import os
from typing import List

import pandas as pd

from config import Settings

logger = logging.getLogger(__name__)


def _sanitize(obj):
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


class ReportGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _path(self, name):
        return os.path.join(self.settings.reports_path, name)

    def _write_json(self, name, data):
        os.makedirs(self.settings.reports_path, exist_ok=True)
        try:
            with open(self._path(name), "w", encoding="utf-8") as f:
                json.dump(_sanitize(data), f, indent=2,
                          ensure_ascii=False, default=str)
            logger.info("Сохранено %s", name)
        except OSError as exc:
            logger.error("Не удалось сохранить %s: %s", name, exc)

    def save_summary(self, data):
        self._write_json("summary.json", data)

    def save_errors(self, errors, limit: int = 50_000):
        self._write_json("errors.json", errors[:limit])

    def save_anomalies(self, anomalies, limit: int = 1000):
        self._write_json("anomalies.json", anomalies[:limit])
        if len(anomalies) > limit:
            logger.info("anomalies.json усечён до %d из %d записей",
                        limit, len(anomalies))

    def save_text_report(self, text):
        os.makedirs(self.settings.reports_path, exist_ok=True)
        try:
            with open(self._path("report.txt"), "w", encoding="utf-8") as f:
                f.write(text)
            logger.info("Сохранено report.txt")
        except OSError as exc:
            logger.error("Не удалось сохранить report.txt: %s", exc)

    def _save_csv(self, name, df: pd.DataFrame):
        os.makedirs(self.settings.reports_path, exist_ok=True)
        try:
            df.to_csv(self._path(name), index=False)
            logger.info("Сохранено %s", name)
        except OSError as exc:
            logger.error("Не удалось сохранить %s: %s", name, exc)

    def save_servers_csv(self, df: pd.DataFrame):
        self._save_csv("servers.csv", df)

    def save_statistics_csv(self, df: pd.DataFrame):
        self._save_csv("statistics.csv", df)

    def save_problem_servers_csv(self, df: pd.DataFrame):
        self._save_csv("problem_servers.csv", df)