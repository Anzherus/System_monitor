import json, logging, os
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Optional, get_type_hints

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"


def _coerce(value, expected):
    """Приводит значение из JSON к ожидаемому типу. Возвращает (value, ok)."""
    if expected is int:
        if isinstance(value, bool):
            return None, False
        if isinstance(value, int):
            return value, True
        if isinstance(value, str):
            try:
                return int(value), True
            except ValueError:
                return None, False
        return None, False
    if expected is float:
        if isinstance(value, bool):
            return None, False
        if isinstance(value, (int, float)):
            return float(value), True
        if isinstance(value, str):
            try:
                return float(value), True
            except ValueError:
                return None, False
        return None, False
    if expected is str:
        if isinstance(value, str):
            return value, True
        return None, False
    return value, True


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
        if not os.path.exists(path):
            settings = cls()
            settings.save(path)
            return settings

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Не удалось загрузить настройки из %s: %s. "
                           "Используются значения по умолчанию.", path, exc)
            settings = cls()
            settings.save(path)
            return settings

        if not isinstance(data, dict):
            logger.warning("settings.json должен содержать объект, получено %s",
                           type(data).__name__)
            settings = cls()
            settings.save(path)
            return settings

        hints = get_type_hints(cls)
        valid = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            expected = hints.get(f.name, f.type)
            coerced, ok = _coerce(data[f.name], expected)
            if ok:
                valid[f.name] = coerced
            else:
                logger.warning("Неверное значение настройки %s=%r "
                               "(ожидалось %s). Используется значение по умолчанию.",
                               f.name, data[f.name], getattr(expected, "__name__", expected))

        return cls(**valid)

    def save(self, path: Optional[str] = None) -> None:
        path = path or str(DATA_DIR / "settings.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Не удалось сохранить настройки в %s: %s", path, exc)


def ensure_dirs(settings: Settings) -> None:
    for p in (settings.data_path, settings.logs_path, settings.reports_path):
        os.makedirs(p, exist_ok=True)