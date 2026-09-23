"""
Численный анализ метрик и обнаружение аномалий.
"""
import logging
import math
from array import array
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("CPU usage: ", "cpu"),
    ("Memory usage: ", "ram"),
    ("Disk usage: ", "disk"),
    ("Network throughput: ", "net"),
)


def extract_metrics(message):
    out: Dict[str, float] = {}
    for prefix, key in _PREFIXES:
        pos = message.find(prefix)
        if pos < 0:
            continue
        if pos > 0 and message[pos - 1].isalnum():
            continue
        rest = message[pos + len(prefix):]
        i = 0
        while i < len(rest) and rest[i].isdigit():
            i += 1
        if i:
            out[key] = float(rest[:i])
    return out


class _Welford:
    __slots__ = ("n", "mean", "M2")

    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0

    def update(self, x):
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.M2 += delta * (x - self.mean)

    @property
    def variance(self):
        return self.M2 / self.n if self.n > 1 else 0.0

    @property
    def std(self):
        return math.sqrt(self.variance)


class NumericAnalyzer:
    METRICS = ("cpu", "ram", "disk", "net")

    def __init__(self):
        self.buffers: Dict[str, array] = {m: array("d") for m in self.METRICS}

    def feed(self, record):
        for k, v in extract_metrics(record.get("message", "")).items():
            self.buffers[k].append(v)

    def result(self):
        out = {}
        for m, buf in self.buffers.items():
            if not buf:
                continue
            arr = np.frombuffer(buf, dtype=np.float64)
            out[m] = {
                "count": int(arr.size),
                "mean": float(np.mean(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "median": float(np.median(arr)),
                "std": float(np.std(arr)),
            }
        return out


class PerServerNumericAnalyzer:
    
    METRICS = ("cpu", "ram", "disk", "net")

    def __init__(self):
        self._stats: Dict[str, Dict[str, _Welford]] = {}

    def feed(self, record):
        metrics = extract_metrics(record.get("message", ""))
        if not metrics:
            return
        server = record.get("server", "?")
        srv_stats = self._stats.get(server)
        if srv_stats is None:
            srv_stats = {m: _Welford() for m in self.METRICS}
            self._stats[server] = srv_stats
        for m, v in metrics.items():
            srv_stats[m].update(v)

    def per_server(self):
        out: Dict[str, Dict[str, dict]] = {}
        for srv, metrics in self._stats.items():
            entry: Dict[str, dict] = {}
            for m, w in metrics.items():
                if w.n > 0:
                    entry[m] = {
                        "count": w.n,
                        "mean": round(w.mean, 2),
                        "std": round(w.std, 2),
                    }
            if entry:
                out[srv] = entry
        return out


class AnomalyDetector:
    

    def __init__(self, threshold: float = 2.0, min_samples: int = 30):
        self.threshold = threshold
        self.min_samples = min_samples
        self._stats: Dict[Tuple[str, str], _Welford] = {}
        self._anomalies: List[dict] = []

    def feed(self, record):
        server = record.get("server", "?")
        ts_iso = record["timestamp"].isoformat()
        for m, v in extract_metrics(record.get("message", "")).items():
            key = (server, m)
            w = self._stats.get(key)
            if w is None:
                w = _Welford()
                self._stats[key] = w

            if w.n >= self.min_samples and w.std > 0:
                z = abs(v - w.mean) / w.std
                if z > self.threshold:
                    self._anomalies.append({
                        "server": server,
                        "metric": m,
                        "value": v,
                        "z_score": round(z, 2),
                        "timestamp": ts_iso,
                    })
            w.update(v)

    def result(self):
        return self._anomalies

    def stats_summary(self):
        out: Dict[str, Dict[str, dict]] = {}
        for (srv, metric), w in self._stats.items():
            out.setdefault(srv, {})[metric] = {
                "mean": round(w.mean, 2),
                "std": round(w.std, 2),
                "count": w.n,
            }
        return out