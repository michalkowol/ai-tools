"""Read side of the Worklog: entry queries and the generated day Markdown."""
from __future__ import annotations

import datetime as dt
import os
import threading
from typing import Any

from . import core


def _months_between(since: dt.date, until: dt.date) -> list[str]:
    months, cursor = [], since.replace(day=1)
    while cursor <= until:
        months.append(cursor.strftime("%Y-%m"))
        cursor = (cursor + dt.timedelta(days=32)).replace(day=1)
    return months


def entries(
    since: dt.date,
    until: dt.date | None = None,
    jira: str | None = None,
) -> list[dict[str, Any]]:
    """Entries whose date is in [since, until], chronological, de-duplicated by id."""
    until = until or core.now().date()
    seen: dict[str, dict[str, Any]] = {}
    for month in _months_between(since, until):
        for path in sorted((core.entries_dir() / month).glob("*.jsonl")):
            for row in core.read_jsonl(path):
                day = dt.date.fromisoformat(row.get("date") or row["to_ts"][:10])
                if not since <= day <= until:
                    continue
                if jira and (row.get("jira") or "").upper() != jira.upper():
                    continue
                seen.setdefault(row["id"], row)
    return sorted(seen.values(), key=lambda r: (r.get("from_ts") or "", r["id"]))


def open_threads(since: dt.date) -> list[dict[str, Any]]:
    """The latest entry of every session since `since` that is not done or has
    next steps or blockers: unfinished work for the day plan."""
    latest: dict[str, dict[str, Any]] = {}
    for row in entries(since):
        latest[row["session_id"]] = row
    return [
        r for r in latest.values()
        if r.get("status") != "done" or r.get("next_steps") or r.get("blockers")
    ]


def _hhmm(ts: str) -> str:
    return core.parse_ts(ts).strftime("%H:%M")


def render_day(day: str) -> str:
    rows = entries(dt.date.fromisoformat(day), dt.date.fromisoformat(day))
    lines = [f"# Worklog {day}", ""]
    if not rows:
        lines.append("No entries.")
        return "\n".join(lines) + "\n"
    for r in rows:
        where = " / ".join(x for x in (r.get("repo"), r.get("worktree") or r.get("branch")) if x)
        head = " · ".join(x for x in (f"{_hhmm(r['from_ts'])}–{_hhmm(r['to_ts'])}", where, r.get("jira"), r.get("status")) if x)
        lines += [f"## {head}", "", r.get("summary") or "", ""]
        for label, key in (
            ("Done", "accomplished"),
            ("Decisions", "decisions"),
            ("Problems solved", "problems_solved"),
            ("Blockers", "blockers"),
            ("Next", "next_steps"),
        ):
            for item in r.get(key) or []:
                lines.append(f"- **{label}:** {item}")
        meta = []
        if r.get("signals"):
            meta.append("events: " + ", ".join(r["signals"]))
        if r.get("tags"):
            meta.append("tags: " + ", ".join(r["tags"]))
        meta.append(f"session: `{r['session_id']}`")
        lines += ["", "_" + " · ".join(meta) + "_", ""]
    return "\n".join(lines).rstrip() + "\n"


def write_day(day: str) -> None:
    core.days_dir().mkdir(parents=True, exist_ok=True)
    path = core.days_dir() / f"{day}.md"
    # The day view is regenerated from entries, so a concurrent rewrite from
    # another container or thread is harmless as long as each one replaces atomically.
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(render_day(day), encoding="utf-8")
    os.replace(tmp, path)


def context(today: dt.date) -> dict[str, Any]:
    """Worklog context for the day plan: entries since the last workday and open threads."""
    since = core.last_workday(today)
    return {
        "today": today.isoformat(),
        "last_workday": since.isoformat(),
        "entries": entries(since, today),
        "open_threads": open_threads(today - dt.timedelta(days=14)),
    }
