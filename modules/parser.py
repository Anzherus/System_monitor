import logging
from datetime import datetime
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

_LEVELS = {"INFO", "WARNING", "ERROR", "CRITICAL"}


def _parse_timestamp(s: str) -> Optional[datetime]: 
    if len(s) < 19:
        return None
    if s[4] != "-" or s[7] != "-" or s[10] != " " or s[13] != ":" or s[16] != ":":
        return None
    try:
        return datetime(
            int(s[0:4]), int(s[5:7]), int(s[8:10]),
            int(s[11:13]), int(s[14:16]), int(s[17:19]),
        )
    except (ValueError, TypeError):
        return None


def parse_log_line(line: str) -> Optional[dict]:
    line = line.strip()
    if not line:
        return None
    parts = line.split("|", 3)
    if len(parts) < 4:
        return None

    ts = _parse_timestamp(parts[0].strip())
    if ts is None:
        return None

    level = parts[2].strip().upper()
    if level not in _LEVELS:
        return None

    return {
        "date": ts.date().isoformat(),
        "time": ts.time().isoformat(),
        "timestamp": ts,
        "server": parts[1].strip(),
        "level": level,
        "message": parts[3].strip(),
    }


def iter_log_file(path: str) -> Iterator[dict]:
    skipped = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for lineno, raw in enumerate(f, 1):
                rec = parse_log_line(raw)
                if rec is None:
                    skipped += 1
                    if skipped <= 5:
                        logger.warning("Некорректная запись %s:%d пропущена", path, lineno)
                    continue
                yield rec
    except FileNotFoundError:
        logger.error("Файл лога не найден: %s", path)
    except OSError as exc:
        logger.error("Не удалось прочитать %s: %s", path, exc)
    if skipped:
        logger.info("%s: пропущено %d некорректных строк", path, skipped)


def parse_log_file(path: str) -> list:
    return list(iter_log_file(path))