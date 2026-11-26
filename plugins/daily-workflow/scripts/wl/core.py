"""Shared helpers: paths, time, config, JSONL files, locks and git."""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import json
import os
import re
import shutil
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any, Iterator

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = PLUGIN_ROOT / "config.example.toml"

DEFAULT_CONFIG: dict[str, Any] = {
    "worklog": {
        "model": "claude-haiku-5-5",
        "summary_threshold_minutes": 15,
        "jira_project_keys": [],
        "summary_timeout_seconds": 240,
    },
}


def home() -> Path:
    return Path(os.environ.get("WORKLOG_HOME") or Path.home() / ".ai" / "worklog").expanduser()


def checkpoints_dir() -> Path:
    return home() / "checkpoints"


def state_dir() -> Path:
    return home() / "state" / "sessions"


def cursors_dir() -> Path:
    return home() / "state" / "cursors"


def entries_dir() -> Path:
    return home() / "entries"


def days_dir() -> Path:
    return home() / "days"


def plans_dir() -> Path:
    return home() / "plans"


def meetings_dir() -> Path:
    return home() / "meetings"


def locks_dir() -> Path:
    return home() / "locks"


def logs_dir() -> Path:
    return home() / "logs"


def log(message: str) -> None:
    try:
        logs_dir().mkdir(parents=True, exist_ok=True)
        stamp = now().isoformat(timespec="seconds")
        with open(logs_dir() / "worklog.log", "a", encoding="utf-8") as fh:
            fh.write(f"{stamp} [pid={os.getpid()}] {message}\n")
    except OSError:
        pass


# ---------------------------------------------------------------- config

_config_cache: dict[str, Any] | None = None


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def config() -> dict[str, Any]:
    global _config_cache
    if _config_cache is None:
        path = home() / "config.toml"
        loaded: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = tomllib.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # broken config must not break hooks
                log(f"[config] failed to parse {path}: {exc}")
        _config_cache = _merge(DEFAULT_CONFIG, loaded)
    return _config_cache


def reset_config_cache() -> None:
    global _config_cache
    _config_cache = None


# ---------------------------------------------------------------- time

def now() -> dt.datetime:
    """Container local time; the launcher sets TZ to the host time zone."""
    return dt.datetime.now().astimezone()


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def parse_ts(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def last_workday(day: dt.date) -> dt.date:
    prev = day - dt.timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= dt.timedelta(days=1)
    return prev


# ---------------------------------------------------------------- files

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                log(f"[jsonl] skipped a broken line in {path}")
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


@contextlib.contextmanager
def file_lock(name: str, blocking: bool = True, timeout: float = 10.0) -> Iterator[bool]:
    """flock-based lock. Only used between processes of one session, which all
    run in the same container, so flock is reliable here. Yields False when the
    lock is busy and blocking is False or the timeout passes."""
    locks_dir().mkdir(parents=True, exist_ok=True)
    fh = open(locks_dir() / f"{name}.lock", "a+")
    acquired = False
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if not blocking or time.monotonic() > deadline:
                    break
                time.sleep(0.05)
        yield acquired
    finally:
        if acquired:
            fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


# ---------------------------------------------------------------- git

def run(cmd: list[str], cwd: str | Path | None = None, timeout: float = 5.0) -> str | None:
    try:
        out = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def git(cwd: str | Path, *args: str, timeout: float = 5.0) -> str | None:
    return run(["git", "-c", "safe.directory=*", "-C", str(cwd), *args], timeout=timeout)


def ensure_home() -> Path:
    """Create the Worklog directory, its git repo and config.toml on first use."""
    root = home()
    for sub in ("checkpoints", "state/sessions", "state/cursors", "entries", "days", "plans", "inbox", "meetings", "locks", "logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("locks/\nlogs/\n*.tmp\n", encoding="utf-8")
    config_path = root / "config.toml"
    if not config_path.exists() and EXAMPLE_CONFIG.exists():
        shutil.copyfile(EXAMPLE_CONFIG, config_path)
    if not (root / ".git").exists():
        git(root, "init", "-q")
    return root


def commit_worklog(message: str, attempts: int = 5) -> bool:
    """Commit everything in the Worklog repo. Another container may hold
    index.lock, so retry a few times and give up quietly: the next commit
    picks the changes up."""
    root = home()
    if not (root / ".git").exists():
        return False
    for attempt in range(attempts):
        if git(root, "add", "-A", timeout=20) is not None:
            if not git(root, "status", "--porcelain", timeout=20):
                return True
            committed = git(
                root,
                "-c", "user.name=worklog",
                "-c", "user.email=worklog@localhost",
                "commit", "-q", "--no-verify", "-m", message,
                timeout=20,
            )
            if committed is not None:
                return True
        time.sleep(0.5 * (attempt + 1))
    log(f"[git] commit failed after {attempts} attempts: {message}")
    return False


# ---------------------------------------------------------------- misc

def truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


JIRA_KEY = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")


def find_jira_key(*candidates: str | None) -> str | None:
    allowed = [k.upper() for k in (config()["worklog"].get("jira_project_keys") or [])]
    for candidate in candidates:
        if not candidate:
            continue
        for match in JIRA_KEY.finditer(candidate.upper()):
            key = match.group(1)
            if not allowed or key.split("-")[0] in allowed:
                return key
    return None
