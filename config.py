import json, logging, os
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"


@dataclass
class Settings:
    max_threads: int = 4
    processes: int = 4
    logs_path: str = str(LOGS_DIR)
    data_path: str = str(DATA_DIR)
    reports_path: str = str(REPORTS_DIR)
    anomaly_threshold: float = 2.0
    test_servers: int = 50
    test_logs: int = 100000

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Settings":
        path = path or str(DATA_DIR / "settings.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                valid = {k: v for k, v in data.items()
                         if k in {f.name for f in fields(cls)}}
                return cls(**valid)
            except (json.JSONDecodeError, TypeError, OSError) as exc:
                logger.warning("Не удалось загрузить настройки из %s: %s", path, exc)
                # Создаем новый файл с дефолтными настройками
                settings = cls()
                settings.save(path)
                return settings
        else:
            # Создаем директорию и файл с дефолтными настройками
            settings = cls()
            settings.save(path)
            return settings

    def save(self, path: Optional[str] = None) -> None:
        path = path or str(DATA_DIR / "settings.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)


def ensure_dirs(settings: Settings) -> None:
    for p in (settings.data_path, settings.logs_path, settings.reports_path):
        os.makedirs(p, exist_ok=True)