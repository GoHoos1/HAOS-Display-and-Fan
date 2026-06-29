from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
import os
from pathlib import Path
import shutil
import socket
import time


@dataclass
class SystemMetrics:
    hostname: str
    ip: str
    time: str
    date: str
    uptime: str
    uptime_seconds: int
    cpu_temp_c: str
    cpu_load_1m: float
    mem_percent: int
    disk_percent: int

    def as_tokens(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def read_cpu_temp(path: str = "/sys/class/thermal/thermal_zone0/temp") -> str:
    try:
        raw = Path(path).read_text(encoding="utf-8").strip()
        return f"{int(raw) / 1000:.1f}"
    except (FileNotFoundError, PermissionError, ValueError):
        return "--"


def read_load_average() -> float:
    try:
        return float(Path("/proc/loadavg").read_text(encoding="utf-8").split()[0])
    except (FileNotFoundError, IndexError, ValueError):
        return 0.0


def read_memory_percent() -> int:
    try:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0])
        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", 0)
        return round((total - available) / total * 100) if total else 0
    except (FileNotFoundError, ValueError, IndexError):
        return 0


def read_primary_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "0.0.0.0"
    finally:
        sock.close()


def read_uptime() -> tuple[str, int]:
    try:
        seconds = int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
    except (FileNotFoundError, ValueError, IndexError):
        seconds = int(time.monotonic())
    return str(timedelta(seconds=seconds)).split(".", 1)[0], seconds


def collect_metrics() -> SystemMetrics:
    now = time.localtime()
    uptime_text, uptime_seconds = read_uptime()
    disk = shutil.disk_usage("/")
    return SystemMetrics(
        hostname=socket.gethostname(),
        ip=read_primary_ip(),
        time=time.strftime("%H:%M:%S", now),
        date=time.strftime("%Y-%m-%d", now),
        uptime=uptime_text,
        uptime_seconds=uptime_seconds,
        cpu_temp_c=read_cpu_temp(),
        cpu_load_1m=read_load_average(),
        mem_percent=read_memory_percent(),
        disk_percent=round(disk.used / disk.total * 100) if disk.total else 0,
    )


def architecture() -> str:
    return os.uname().machine if hasattr(os, "uname") else "unknown"
