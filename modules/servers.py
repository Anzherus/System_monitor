"""Управление серверами и приоритезация."""
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Optional
from config import Settings
from modules.storage import load_json, save_json
from utils.validators import validate_server

logger = logging.getLogger(__name__)


class Priority(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def compute_priority(errors: int, critical: int,
                     warnings: int, total: int = 0) -> Priority:
    if total > 0:
        crit_rate = critical / total
        err_rate = errors / total
        warn_rate = warnings / total

        if crit_rate >= 0.01 or (critical >= 1000 and crit_rate >= 0.005):
            return Priority.CRITICAL
        if err_rate >= 0.05 or crit_rate >= 0.002:
            return Priority.HIGH
        if err_rate >= 0.02 or warn_rate >= 0.20:
            return Priority.WARNING
        return Priority.NORMAL

    if critical >= 10 or errors >= 100:
        return Priority.CRITICAL
    if critical >= 1 or errors >= 20:
        return Priority.HIGH
    if errors >= 5 or warnings >= 50:
        return Priority.WARNING
    return Priority.NORMAL


@dataclass
class Server:
    id: int
    name: str
    os: str
    ip: str
    environment: str
    cpu: int
    ram: int
    status: str

    def to_dict(self) -> dict:
        return asdict(self)


class ServerManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.servers: List[Server] = []
        self.path = f"{settings.data_path}/servers.json"

    def load(self) -> int:
        raw = load_json(self.path)
        if not raw:
            return 0
        self.servers = []
        for item in raw:
            ok, err = validate_server(item)
            if not ok:
                logger.warning("Пропущен некорректный сервер %s: %s", item, err)
                continue
            self.servers.append(Server(**{k: item[k] for k in (
                "id", "name", "os", "ip", "environment", "cpu", "ram", "status")}))
        logger.info("Загружено %d серверов", len(self.servers))
        return len(self.servers)

    def save(self) -> bool:
        return save_json(self.path, [s.to_dict() for s in self.servers])

    def all(self) -> List[Server]:
        return list(self.servers)

    def active(self) -> List[Server]:
        return [s for s in self.servers if s.status == "active"]

    def find(self, query: str) -> List[Server]:
        q = query.lower()
        return [s for s in self.servers if q in s.name.lower() or q in s.ip.lower()]

    def get_by_name(self, name: str) -> Optional[Server]:
        for s in self.servers:
            if s.name == name:
                return s
        return None