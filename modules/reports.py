import json, logging, os
from typing import List
import pandas as pd
from config import Settings

logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _path(self, name: str) -> str:
        return os.path.join(self.settings.reports_path, name)

    def save_summary(self, data: dict) -> None:
        with open(self._path("summary.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Сохранено summary.json")

    def save_errors(self, errors: List[dict]) -> None:
        with open(self._path("errors.json"), "w", encoding="utf-8") as f:
            json.dump(errors[:10000], f, indent=2, ensure_ascii=False)
        logger.info("Сохранено errors.json (%d)", len(errors))

    def save_text_report(self, text: str) -> None:
        with open(self._path("report.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        logger.info("Сохранено report.txt")

    def save_servers_csv(self, df: pd.DataFrame) -> None:
        df.to_csv(self._path("servers.csv"), index=False)
        logger.info("Сохранено servers.csv")

    def save_statistics_csv(self, df: pd.DataFrame) -> None:
        df.to_csv(self._path("statistics.csv"), index=False)
        logger.info("Сохранено statistics.csv")
        


