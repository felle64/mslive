from __future__ import annotations

import time
from pathlib import Path
from typing import Optional


def timestamp_for_filename(now: Optional[float] = None) -> str:
    t = time.time() if now is None else now
    return time.strftime("%Y%m%d_%H%M%S", time.localtime(t))


def default_log_name(profile: str, mode: str, suffix: str = ".csv") -> str:
    ts = timestamp_for_filename()
    return f"{profile}_{mode}_{ts}{suffix}"


def logs_dir(base: Optional[Path] = None) -> Path:
    root = Path.cwd() if base is None else base
    return root / "logs"


def ensure_logs_dir(base: Optional[Path] = None) -> Path:
    p = logs_dir(base=base)
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_log_path(path_arg: Optional[str], default_name: str, base: Optional[Path] = None) -> Path:
    logs_root = ensure_logs_dir(base=base)
    if not path_arg:
        p = logs_root / default_name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    p = Path(path_arg)
    if not p.is_absolute():
        p = logs_root / p

    p.parent.mkdir(parents=True, exist_ok=True)
    return p
