import logging, os, random
from datetime import datetime, timedelta
from typing import List
from config import Settings
from modules.servers import Server, ServerManager
from modules.storage import save_json

logger = logging.getLogger(__name__)

OS_CHOICES = ["Linux", "Windows Server", "FreeBSD", "Ubuntu"]
ENVS = ["production", "staging", "development"]
STATUSES = ["active", "active", "active", "inactive", "maintenance"]
LEVELS = ["INFO"] * 80 + ["WARNING"] * 13 + ["ERROR"] * 6 + ["CRITICAL"]
ERROR_MSGS = [
    "Database connection timeout",
    "Disk I/O error",
    "Network unreachable",
    "Service crashed",
    "Authentication failed",
    "Out of memory",
]
WARN_MSGS = [
    "Memory usage high",
    "CPU load elevated",
    "Disk space low",
    "Latency spike",
]


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


def _make_line(ts: datetime, server: str) -> str:
    level = random.choice(LEVELS)
    if level == "INFO":
        metric = random.choice(["CPU usage", "Memory usage", "Disk usage", "Network throughput"])
        value = random.randint(1, 100)
        msg = f"{metric}: {value}"
    elif level == "WARNING":
        msg = random.choice(WARN_MSGS) + f": {random.randint(60, 95)}"
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
    files = files or max(1, min(100, len(servers) * 2))
    os.makedirs(settings.logs_path, exist_ok=True)

    for old in os.listdir(settings.logs_path):
        if old.startswith("server_") and old.endswith(".log"):
            os.remove(os.path.join(settings.logs_path, old))
    per_file = max(1, total_records // files)
    base_time = datetime.now() - timedelta(days=3)
    written = 0

    for fi in range(files):
        path = os.path.join(settings.logs_path, f"server_{fi + 1:03d}.log")
        ts = base_time + timedelta(minutes=fi * 5)
        with open(path, "w", encoding="utf-8") as f:
            for _ in range(per_file):
                ts += timedelta(seconds=random.randint(1, 30))
                srv = random.choice(servers).name
                f.write(_make_line(ts, srv) + "\n")
                written += 1
    logger.info("Сгенерировано %d записей в %d файлах", written, files)
    return written


def generate_infrastructure(settings: Settings,
                            servers_count: int = None,
                            logs_count: int = None) -> None:
    mgr = ServerManager(settings)
    mgr.servers = generate_servers(settings, servers_count)
    mgr.save()
    generate_logs(settings, mgr.servers, logs_count)