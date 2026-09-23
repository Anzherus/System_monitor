import json, logging, os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def load_json(path):
    if not os.path.exists(path):
        logger.warning("Файл не найден: %s", path)
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("Неверный JSON в %s: %s", path, exc)
        return None
    except OSError as exc:
        logger.error("Не удалось прочитать %s: %s", path, exc)
        return None


def save_json(path, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            return True
    except (OSError, TypeError) as exc:
        logger.error("Не удалось записать %s: %s", path, exc)
        return False
    

