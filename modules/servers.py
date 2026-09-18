import logging
from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional
from config import Settings
from modules.storage import load_json, save_json
from utils.validators import validate_server

logger = logging.getLogger(__name__)


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
            self.servers.append(Server(**item))
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
    