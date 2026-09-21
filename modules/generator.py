"""
Генерация тестовой инфраструктуры.
"""
import logging
import os
import random
from datetime import datetime, timedelta
from typing import List

from config import Settings
from modules.servers import Server, ServerManager

logger = logging.getLogger(__name__)

OS_CHOICES = ["Linux", "Windows Server", "FreeBSD", "Ubuntu"]
ENVS = ["production", "staging", "development"]
STATUSES = ["active", "active", "active", "inactive", "maintenance", "unavailable"]

ERROR_MSGS = [
    "Database connection timeout",
    "Disk I/O error",
    "Network unreachable",
    "Service crashed",
    "Authentication failed",
    "Out of memory",
    "SSL handshake failure",
    "Connection reset by peer",
    "Segmentation fault",
    "Configuration file missing",
]
METRIC_NAMES = ["CPU usage", "Memory usage", "Disk usage", "Network throughput"]


def _weighted_choice(pairs) -> str:
    total = sum(w for _, w in pairs)
    r = random.randint(1, total)
    acc = 0
    for item, w in pairs:
        acc += w
        if r <= acc:
            return item
    return pairs[-1][0]


def _metric_value() -> int:
    
    if random.random() < 0.01:
        return random.randint(90, 100)
    return max(1, min(89, int(random.gauss(50, 15))))


def generate_servers(settings: Settings, count: int = None) -> List[Server]:
    count = count or settings.test_servers
    servers = []
    for i in range(1, count + 1):
        servers.append(Server(
            id=i,
            name=f"server-{i:02d}",
            os=random.choice(OS_CHOICES),
            ip=f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}",
            environment=random.choice(ENVS),
            cpu=random.choice([2, 4, 8, 16, 32]),
            ram=random.choice([2, 4, 8, 16, 32]),
            status=random.choice(STATUSES),
        ))
    return servers


def _make_line(ts: datetime, server: str, error_bias: float = 1.0) -> str:
    level = _weighted_choice([
        ("INFO", 820),
        ("WARNING", 130),
        ("ERROR", int(48 * error_bias)),
        ("CRITICAL", int(2 * error_bias)),
    ])
    if level == "INFO":
        msg = f"{random.choice(METRIC_NAMES)}: {_metric_value()}"
    elif level == "WARNING":
        msg = f"{random.choice(METRIC_NAMES)}: {random.randint(75, 92)} (high)"
    elif level == "ERROR":
        msg = random.choice(ERROR_MSGS)
    else:
        msg = "Service unavailable: " + random.choice(ERROR_MSGS)
    return f"{ts.strftime('%Y-%m-%d %H:%M:%S')} | {server} | {level} | {msg}"


def generate_logs(settings: Settings,
                  servers: List[Server],
                  total_records: int = None,
                  files: int = None) -> int:
    total_records = total_records or settings.test_logs
    files = max(1, files or len(servers))
    os.makedirs(settings.logs_path, exist_ok=True)

   
    for old in os.listdir(settings.logs_path):
        if old.startswith("server_") and old.endswith(".log"):
            try:
                os.remove(os.path.join(settings.logs_path, old))
            except OSError as exc:
                logger.warning("Не удалось удалить %s: %s", old, exc)

    server_bias = {s.name: random.uniform(0.5, 2.5) for s in servers}

    per_file = max(1, total_records // files)
    base_time = datetime.now() - timedelta(days=3)
    written = 0

    for fi in range(files):
        srv = servers[fi % len(servers)]
        idx = fi // len(servers) + 1
        safe = srv.name.replace("-", "_")
        path = os.path.join(settings.logs_path, f"{safe}_{idx:03d}.log")

        ts = base_time + timedelta(minutes=fi * 5)
        try:
            with open(path, "w", encoding="utf-8") as f:
                for _ in range(per_file):
                    ts += timedelta(seconds=random.randint(1, 30))
                    f.write(_make_line(ts, srv.name,
                                       server_bias[srv.name]) + "\n")
                    written += 1
        except OSError as exc:
            logger.error("Не удалось записать %s: %s", path, exc)
            break

    logger.info("Сгенерировано %d записей в %d файлах", written, files)
    return written


def generate_infrastructure(settings, servers_count=None,
                            logs_count=None, files_count=None):
    mgr = ServerManager(settings)
    mgr.servers = generate_servers(settings, servers_count)
    mgr.save()
    generate_logs(settings, mgr.servers, logs_count, files_count)