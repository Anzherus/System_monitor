import logging, re
from typing import Dict, List
import numpy as np

logger = logging.getLogger(__name__)

CPU_RE = re.compile(r"CPU usage:\s*(\d+)")
RAM_RE = re.compile(r"Memory usage:\s*(\d+)")
DISK_RE = re.compile(r"Disk usage:\s*(\d+)")
NET_RE = re.compile(r"Network throughput:\s*(\d+)")


def _extract(message: str) -> Dict[str, float]:
    out = {}
    for key, rx in (("cpu", CPU_RE), ("ram", RAM_RE),
                    ("disk", DISK_RE), ("net", NET_RE)):
        m = rx.search(message)
        if m:
            out[key] = float(m.group(1))
    return out


class NumericAnalyzer:
    METRICS = ("cpu", "ram", "disk", "net")

    def __init__(self):
        self.buffers: Dict[str, List[float]] = {m: [] for m in self.METRICS}

    def feed(self, record: dict) -> None:
        for k, v in _extract(record.get("message", "")).items():
            self.buffers[k].append(v)

    def result(self) -> Dict[str, dict]:
        out = {}
        for m, vals in self.buffers.items():
            if not vals:
                continue
            arr = np.asarray(vals, dtype=float)
            out[m] = {
                "count": int(arr.size),
                "mean": float(np.mean(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "median": float(np.median(arr)),
                "std": float(np.std(arr)),
            }
        return out


class AnomalyDetector:
    def __init__(self, threshold: float = 2.0):
        self.threshold = threshold
        self.buffers: Dict[str, List[float]] = {}
        self.records: List[dict] = []

    def feed(self, record: dict) -> None:
        extracted = _extract(record.get("message", ""))
        if not extracted:
            return
        self.records.append(record)
        for k, v in extracted.items():
            self.buffers.setdefault(k, []).append(v)

    def detect(self) -> List[dict]:
        thresholds = {}
        for m, vals in self.buffers.items():
            if len(vals) < 2:
                continue
            arr = np.asarray(vals, dtype=float)
            thresholds[m] = (float(np.mean(arr)), float(np.std(arr)))
        
        anomalies = []
        for rec in self.records:
            extracted = _extract(rec.get("message", ""))
            for m, v in extracted.items():
                if m not in thresholds:
                    continue
                mean, std = thresholds[m]
                if std == 0:
                    continue
                z = abs(v - mean) / std
                if z > self.threshold:
                    anomalies.append({
                        "server": rec["server"],
                        "metric": m,
                        "value": v,
                        "z_score": round(z, 2),
                        "timestamp": rec["timestamp"].isoformat(),
                    })
                    break
        return anomalies