import os
import sys
from datetime import datetime

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_BASENAME = os.path.basename(_HERE).lower()
if _BASENAME in ("tests", "test"):
    _ROOT = os.path.dirname(_HERE)
else:
    _ROOT = _HERE
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
from modules.parser import parse_log_line, iter_log_file, parse_log_file
from modules.analyzer import (
    NumericAnalyzer, AnomalyDetector, PerServerNumericAnalyzer, extract_metrics,
)
from modules.servers import compute_priority, Priority
from modules.statistics import PandasAnalyzer
from utils.validators import validate_server, validate_log_line
from utils.helpers import (
    LogRecordIterator, cached_severity_weight, severity_total,
    chain_files, detect_floods, format_error, format_record,
)


#PARSER

def test_parse_valid_line():
    line = "2026-09-12 10:15:21 | server_01 | INFO | CPU usage: 43"
    rec = parse_log_line(line)
    assert rec is not None
    assert rec["server"] == "server_01"
    assert rec["level"] == "INFO"
    assert rec["message"] == "CPU usage: 43"
    assert rec["date"] == "2026-09-12"
    assert rec["timestamp"] == datetime(2026, 9, 12, 10, 15, 21)


def test_parse_line_with_pipe_in_message():
    line = "2026-09-12 10:15:21 | s1 | ERROR | a | b | c"
    rec = parse_log_line(line)
    assert rec is not None
    assert rec["message"] == "a | b | c"


def test_parse_invalid_lines():
    assert parse_log_line("") is None
    assert parse_log_line("   ") is None
    assert parse_log_line("garbage") is None
    assert parse_log_line("2026-99-99 10:15:21 | x | INFO | msg") is None
    assert parse_log_line("2026-09-12 10:15:21 | x | NOT_A_LEVEL | msg") is None
    assert parse_log_line("2026/09/12 10:15:21 | x | INFO | msg") is None
    assert parse_log_line("2026-09-12 10:15:21 | x | INFO") is None


def test_parse_malformed_timestamp():
    assert parse_log_line("2026-09-12 10:15 | x | INFO | msg") is None
    assert parse_log_line("2026-09-12 99:99:99 | x | INFO | msg") is None


def test_parse_level_case_insensitive():
    line = "2026-09-12 10:15:21 | s1 | warning | msg"
    rec = parse_log_line(line)
    assert rec is not None
    assert rec["level"] == "WARNING"


def test_parse_log_file_missing_file_returns_empty(tmp_path):
    missing = str(tmp_path / "nope.log")
    assert parse_log_file(missing) == []


def test_iter_log_file_skips_garbage(tmp_path):
    p = tmp_path / "mixed.log"
    p.write_text(
        "2026-01-01 10:00:00 | s1 | INFO | ok\n"
        "garbage line\n"
        "2026-01-01 10:00:01 | s1 | ERROR | boom\n"
        "\n",
        encoding="utf-8",
    )
    records = list(iter_log_file(str(p)))
    assert len(records) == 2
    assert records[0]["level"] == "INFO"
    assert records[1]["level"] == "ERROR"


#VALIDATE

def test_validate_server_ok():
    ok, err = validate_server({
        "id": 1, "name": "s", "os": "Linux", "ip": "1.2.3.4",
        "environment": "prod", "cpu": 4, "ram": 8, "status": "active",
    })
    assert ok and err is None


def test_validate_server_missing_fields():
    ok, err = validate_server({"id": 1})
    assert not ok
    assert "Отсутствуют" in err


def test_validate_server_bad_cpu():
    ok, _ = validate_server({
        "id": 1, "name": "s", "os": "L", "ip": "1.2.3.4",
        "environment": "p", "cpu": 0, "ram": 8, "status": "a",
    })
    assert not ok


def test_validate_server_bad_ip():
    ok, err = validate_server({
        "id": 1, "name": "s", "os": "L", "ip": "not-an-ip",
        "environment": "p", "cpu": 4, "ram": 8, "status": "a",
    })
    assert not ok
    assert "IP" in err


def test_validate_log_line():
    ok, _ = validate_log_line("2026-09-12 10:15:21 | s | INFO | msg")
    assert ok
    ok, _ = validate_log_line("not a log line")
    assert not ok


def test_validate_log_line_bad_level():
    ok, err = validate_log_line("2026-09-12 10:15:21 | s | TRACE | msg")
    assert not ok
    assert "уровень" in err.lower() or "level" in err.lower() or "TRACE" in err


# ANALIZER

def test_extract_metrics_single():
    assert extract_metrics("CPU usage: 43") == {"cpu": 43.0}
    assert extract_metrics("Memory usage: 87 (high)") == {"ram": 87.0}
    assert extract_metrics("Database connection timeout") == {}
    assert extract_metrics("") == {}


def test_extract_metrics_multiple():
    msg = "CPU usage: 50, Memory usage: 80"
    got = extract_metrics(msg)
    assert got == {"cpu": 50.0, "ram": 80.0}


def test_extract_metrics_all_four():
    msg = "CPU usage: 10 Disk usage: 20 Network throughput: 30"
    got = extract_metrics(msg)
    assert got == {"cpu": 10.0, "disk": 20.0, "net": 30.0}


def test_extract_metrics_no_false_positive_inside_word():
    assert extract_metrics("XCPU usage: 5") == {}


def test_extract_metrics_no_digits_after_prefix():
    assert extract_metrics("CPU usage: N/A") == {}


def test_extract_metrics_numeric_value():
    """Дробные значения обрезаются на первой нецифре (int-схема)."""
    assert extract_metrics("CPU usage: 43.7") == {"cpu": 43.0}


#NUMERIC_ANALYZER

def test_numeric_analyzer():
    na = NumericAnalyzer()
    na.feed({"message": "CPU usage: 50"})
    na.feed({"message": "CPU usage: 70"})
    res = na.result()
    assert res["cpu"]["count"] == 2
    assert res["cpu"]["mean"] == 60.0
    assert res["cpu"]["min"] == 50.0
    assert res["cpu"]["max"] == 70.0
    assert res["cpu"]["median"] == 60.0


def test_numeric_analyzer_empty():
    na = NumericAnalyzer()
    assert na.result() == {}


def test_numeric_analyzer_multiple_metrics():
    na = NumericAnalyzer()
    na.feed({"message": "CPU usage: 10, Memory usage: 20"})
    na.feed({"message": "CPU usage: 30, Memory usage: 40"})
    res = na.result()
    assert set(res.keys()) == {"cpu", "ram"}
    assert res["cpu"]["mean"] == 20.0
    assert res["ram"]["mean"] == 30.0


# ANOMALY_DEECTOR

def test_anomaly_detector_finds_outlier():
    det = AnomalyDetector(threshold=2.0, min_samples=5)
    ts = datetime(2026, 1, 1, 12, 0, 0)
    for v in [50, 51, 49, 50, 50, 51, 50, 49, 50, 50]:
        det.feed({"message": f"CPU usage: {v}", "server": "s1",
                  "timestamp": ts})
    det.feed({"message": "CPU usage: 200", "server": "s1",
              "timestamp": ts})
    anomalies = det.result()
    assert any(a["value"] == 200 for a in anomalies)
    assert all(a["metric"] == "cpu" for a in anomalies)


def test_anomaly_detector_ignores_warmup():
    det = AnomalyDetector(threshold=2.0, min_samples=10)
    ts = datetime(2026, 1, 1)
    for v in [50, 50, 50, 50, 50, 50, 50, 50, 50, 999]:
        det.feed({"message": f"CPU usage: {v}", "server": "s1",
                  "timestamp": ts})
    assert det.result() == []


def test_anomaly_detector_no_anomalies_on_uniform():
    det = AnomalyDetector(threshold=2.0, min_samples=3)
    ts = datetime(2026, 1, 1)
    for _ in range(20):
        det.feed({"message": "CPU usage: 50", "server": "s1",
                  "timestamp": ts})
    assert det.result() == []


def test_anomaly_detector_stats_summary():
    det = AnomalyDetector(min_samples=2)
    ts = datetime(2026, 1, 1)
    for v in [10, 20, 30]:
        det.feed({"message": f"CPU usage: {v}", "server": "s1",
                  "timestamp": ts})
    summary = det.stats_summary()
    assert "s1" in summary
    assert "cpu" in summary["s1"]
    assert summary["s1"]["cpu"]["count"] == 3


def test_anomaly_detector_per_server_isolation():
    det = AnomalyDetector(threshold=2.0, min_samples=3)
    ts = datetime(2026, 1, 1)
    for _ in range(10):
        det.feed({"message": "CPU usage: 50", "server": "s1",
                  "timestamp": ts})
        det.feed({"message": "CPU usage: 10", "server": "s2",
                  "timestamp": ts})
    assert det.result() == []


def test_per_server_numeric_analyzer():
    psn = PerServerNumericAnalyzer()
    psn.feed({"server": "s1", "message": "CPU usage: 40"})
    psn.feed({"server": "s1", "message": "CPU usage: 60"})
    psn.feed({"server": "s2", "message": "CPU usage: 30"})
    psn.feed({"server": "s1", "message": "Memory usage: 80"})
    got = psn.per_server()
    assert got["s1"]["cpu"]["mean"] == 50.0
    assert got["s1"]["ram"]["mean"] == 80.0
    assert got["s2"]["cpu"]["mean"] == 30.0


def test_per_server_numeric_analyzer_empty():
    psn = PerServerNumericAnalyzer()
    assert psn.per_server() == {}


def test_per_server_numeric_analyzer_ignores_non_metrics():
    psn = PerServerNumericAnalyzer()
    psn.feed({"server": "s1", "message": "Database connection timeout"})
    assert psn.per_server() == {}


# PRIORITY

def test_priority_no_total_fallback():
    assert compute_priority(0, 0, 0) == Priority.NORMAL
    assert compute_priority(10, 0, 0) == Priority.WARNING      
    assert compute_priority(25, 0, 0) == Priority.HIGH         
    assert compute_priority(0, 15, 0) == Priority.CRITICAL     
    assert compute_priority(0, 5, 0) == Priority.HIGH          


def test_priority_with_total():
    assert compute_priority(5, 0, 0, 1000) == Priority.NORMAL
    assert compute_priority(30, 0, 0, 1000) == Priority.WARNING
    assert compute_priority(100, 0, 0, 1000) == Priority.HIGH
    assert compute_priority(0, 20, 0, 1000) == Priority.CRITICAL


def test_priority_does_not_degenerate_on_large_total():
    assert compute_priority(100, 0, 0, 1_000_000) == Priority.NORMAL


def test_priority_critical_rate_boundary():
    assert compute_priority(0, 100, 0, 10_000) == Priority.CRITICAL
    assert compute_priority(0, 50, 0, 10_000) == Priority.HIGH


def test_priority_warning_rate():
    assert compute_priority(0, 0, 200, 1000) == Priority.WARNING


# ITERATOR

def test_log_record_iterator_protocol():
    it = LogRecordIterator(iter([{"x": i} for i in range(5)]), page_size=2)
    assert [next(it)["x"] for _ in range(5)] == [0, 1, 2, 3, 4]
    with pytest.raises(StopIteration):
        next(it)


def test_log_record_iterator_is_iterable():
    it = LogRecordIterator(iter([{"x": 1}]))
    assert iter(it) is it


def test_log_record_iterator_page_size_one():
    it = LogRecordIterator(iter([{"x": 1}, {"x": 2}, {"x": 3}]),
                           page_size=1)
    assert [r["x"] for r in it] == [1, 2, 3]


# HELPERS

def test_severity_total_and_cache():
    assert cached_severity_weight("ERROR") == 3
    assert cached_severity_weight("UNKNOWN") == 0
    assert severity_total({"INFO": 2, "WARNING": 1, "ERROR": 3}) == 13


def test_severity_total_empty():
    assert severity_total({}) == 0


def test_chain_files():
    a = iter([{"x": 1}, {"x": 2}])
    b = iter([{"x": 3}])
    assert [r["x"] for r in chain_files([a, b])] == [1, 2, 3]


def test_detect_floods():
    from utils.helpers import detect_floods
    records = [
        {"server": "s1", "message": "DB timeout"},
        {"server": "s1", "message": "DB timeout"},
        {"server": "s1", "message": "DB timeout"},
        {"server": "s1", "message": "other"},
        {"server": "s2", "message": "boom"},
    ]
    floods = list(detect_floods(records, min_run=3))
    assert len(floods) == 1
    assert floods[0]["server"] == "s1"
    assert floods[0]["count"] == 3


def test_detect_floods_below_min_run():
    records = [
        {"server": "s1", "message": "a"},
        {"server": "s1", "message": "a"},
    ]
    assert list(detect_floods(records, min_run=3)) == []


def test_detect_floods_empty():
    assert list(detect_floods([], min_run=1)) == []


def test_format_record_and_partial():
    rec = {"date": "2026-01-01", "time": "10:00:00", "server": "s1",
           "level": "ERROR", "message": "boom"}
    assert format_record("", rec).startswith("2026-01-01")
    assert "s1" in format_record("", rec)
    assert "ERROR" in format_record("", rec)
    assert format_error(rec).startswith("[ERR]")




def _sample_records():
    return [
        {"date": "2026-01-01", "time": "10:00:00.000000", "server": "s1",
         "level": "ERROR", "message": "boom"},
        {"date": "2026-01-01", "time": "10:05:00.000000", "server": "s1",
         "level": "INFO", "message": "ok"},
        {"date": "2026-01-01", "time": "11:00:00.000000", "server": "s2",
         "level": "WARNING", "message": "hmm"},
        {"date": "2026-01-01", "time": "11:10:00.000000", "server": "s2",
         "level": "CRITICAL", "message": "fire"},
    ]


def test_pandas_from_records():
    pa = PandasAnalyzer.from_records(_sample_records())
    bys = pa.by_server()
    assert len(bys) == 2
    byh = pa.by_time_period()
    assert set(byh["hour"]) == {"10", "11"}
    assert byh["count"].sum() == 4


def test_pandas_by_level():
    pa = PandasAnalyzer.from_records(_sample_records())
    levels = pa.by_level()
    assert set(levels["level"]) == {"INFO", "WARNING", "ERROR", "CRITICAL"}
    assert levels["count"].sum() == 4


def test_pandas_by_date():
    pa = PandasAnalyzer.from_records(_sample_records())
    df = pa.by_date()
    assert df.iloc[0]["date"] == "2026-01-01"
    assert df.iloc[0]["count"] == 4


def test_pandas_top_error_messages():
    pa = PandasAnalyzer.from_records(_sample_records())
    df = pa.top_error_messages(n=5)
    assert not df.empty
    assert df.iloc[0]["message"] == "boom"


def test_pandas_filter_min_errors():
    pa = PandasAnalyzer.from_records(_sample_records())
    df = pa.filter_min_errors(threshold=1)
    assert set(df["server"]) == {"s1"}


def test_pandas_problem_servers_has_priority():
    pa = PandasAnalyzer.from_records(_sample_records())
    df = pa.problem_servers()
    assert "priority" in df.columns
    s2 = df[df["server"] == "s2"].iloc[0]
    assert s2["priority"] in ("HIGH", "CRITICAL")


def test_pandas_describe():
    pa = PandasAnalyzer.from_records(_sample_records())
    d = pa.describe()
    assert "mean" in d
    assert "std" in d
    assert "total" in d["mean"]


def test_pandas_per_server_avg_cpu():
    records = [
        {"date": "2026-01-01", "time": "10:00:00", "server": "s1",
         "level": "INFO", "message": "CPU usage: 50"},
        {"date": "2026-01-01", "time": "10:01:00", "server": "s1",
         "level": "INFO", "message": "CPU usage: 70"},
        {"date": "2026-01-01", "time": "10:02:00", "server": "s2",
         "level": "INFO", "message": "CPU usage: 30"},
    ]
    pa = PandasAnalyzer.from_records(records)
    df = pa.by_server()
    assert "avg_cpu" in df.columns
    s1 = df[df["server"] == "s1"].iloc[0]
    assert not pd.isna(s1["avg_cpu"])
    assert abs(s1["avg_cpu"] - 60.0) < 0.1
    s2 = df[df["server"] == "s2"].iloc[0]
    assert not pd.isna(s2["avg_cpu"])
    assert abs(s2["avg_cpu"] - 30.0) < 0.1


def test_pandas_per_server_avg_ram():
    records = [
        {"date": "2026-01-01", "time": "10:00:00", "server": "s1",
         "level": "INFO", "message": "Memory usage: 40"},
        {"date": "2026-01-01", "time": "10:01:00", "server": "s1",
         "level": "INFO", "message": "Memory usage: 60"},
    ]
    pa = PandasAnalyzer.from_records(records)
    df = pa.by_server()
    assert "avg_ram" in df.columns
    assert not pd.isna(df.iloc[0]["avg_ram"])
    assert abs(df.iloc[0]["avg_ram"] - 50.0) < 0.1


def test_pandas_empty():
    pa = PandasAnalyzer.from_records([])
    assert pa.by_server().empty
    levels_df = pa.by_level()
    assert levels_df.empty
    assert pa.describe() == {}



def test_project_root_importable():
    import config
    import modules.parser
    import modules.analyzer
    import modules.statistics
    import utils.helpers
    assert config is not None