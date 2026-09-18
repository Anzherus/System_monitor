import logging
from datetime import datetime
from typing import Iterator, Optional, Tuple
from utils.validators import validate_log_line

logger = logging.getLogger(__name__)


def parse_log_line(line: str) -> Optional[dict]:
    line = line.strip()
    if not line:
        return None
    ok, err = validate_log_line(line)
    if not ok:
        return None
    parts = [p.strip() for p in line.split("|", 3)]
    ts = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
    return {
        "date": ts.date().isoformat(),
        "time": ts.time().isoformat(),
        "timestamp": ts,
        "server": parts[1],
        "level": parts[2].upper(),
        "message": parts[3],
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
                        logger.warning("Некорректная запись лога %s:%d пропущена", path, lineno)
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