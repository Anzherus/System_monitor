from datetime import datetime
from typing import Optional, Tuple

LEVELS = {'INFO', "WARNING", "ERROR", "CRITICAL"}


def validate_server(data: dict) -> Tuple[bool, Optional[str]]:
    required = {'id', "name", "os", "ip", "environment", "cpu", "ram", "status"}
    missing = required - set(data.keys())
    if missing:
        return False, f"Отсутствуют поля: {missing}"
    if not isinstance(data["cpu"], int) or data["cpu"] <= 0:
        return False, "CPU должен быть положительным целым числом"
    if not isinstance(data["ram"], int) or data["ram"] <= 0:
        return False, "RAM должен быть положительным целым числом"
    return True, None


def validate_log_line(line: str) -> Tuple[bool, Optional[str]]:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 4:
        return False, "Недостаточно полей"
    try:
        datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False, "Неверная временная метка"
    if parts[2].upper() not in LEVELS:
        return False, f"Неизвестный уровень: {parts[2]}"
    return True, None
