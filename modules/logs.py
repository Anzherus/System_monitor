import glob, logging, os
from typing import Iterable, Iterator, List
from modules.parser import iter_log_file
from utils.helpers import LogRecordIterator, chain_files

logger = logging.getLogger(__name__)


class LogManager:
    def __init__(self, logs_path: str):
        self.logs_path = logs_path

    def files(self) -> List[str]:
        pattern = os.path.join(self.logs_path, "*.log")
        return sorted(glob.glob(pattern))

    def iter_records(self) -> Iterator[dict]:
        return chain_files(iter_log_file(p) for p in self.files())

    def paginated_records(self, page_size: int = 100) -> LogRecordIterator:
        return LogRecordIterator(self.iter_records(), page_size=page_size)
