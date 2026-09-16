import logging, os, random
from datetime import datetime, timedelta
from typing import List
from config import Settings
from modules.servers import Server, ServerManager
from module.storage import save_json

logger = logging.getLogger(__name__)

OS_CHOICES = ["Linux", "Window Server", "FreeBSD", "Ubuntu"]
ENVS = ["productiojn", "staging", "development"]
STATUSES = ["active", "active", "active", "inactive", "maintenance"]
LEVELS=["INFO"]*80+["WARNING"]*13+["ERROR"]*6+["CRITICAL"]
ERROR_MSGS=[
    "datebase connection timeout",
    "Disk I/O error", 
    "Network unreachable",
    "Service crashed",
    "Authentication failed",
    "Out of memory",
]
WARN_MSGS=[
    "Memory usage high",
    "CPU load elevated",
    "Disk space low", 
    "Latency spike",
]
