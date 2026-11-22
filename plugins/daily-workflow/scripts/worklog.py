#!/usr/bin/env python3
"""Worklog CLI: hook handler, summarizer, queries and plan rendering.

Usage (the most common ones):
  worklog.py hook <Event>                 # called by Claude Code hooks, JSON on stdin
  worklog.py flush [--session ID]         # /worklog: checkpoint + summary now
  worklog.py summarize --all              # catch-up of every unprocessed session
  worklog.py context                      # Worklog context for the briefing (JSON)
  worklog.py github                       # pull request data for the briefing (JSON)
  worklog.py render-plan plans/2026-11-23.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wl import collector, core, github, plan, summarizer, views  # noqa: E402


def host_path(path: Path) -> str:
    """Same path on the host and in the container thanks to the volume."""
    try:
        return "~/" + str(path.resolve().relative_to(Path.home().resolve()))
    except ValueError:
        return str(path)


def dump(data) -> None:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def parse_date(value: str | None) -> dt.date:
    return dt.date.fromisoformat(value) if value else core.now().date()


def transcript_guess(session_id: str, cwd: str) -> str | None:
    folder = re.sub(r"[^A-Za-z0-9]", "-", cwd)
    path = Path.home() / ".claude" / "projects" / folder / f"{session_id}.jsonl"
    return str(path) if path.exists() else None


def resolve_session(value: str | None) -> str | None:
    if value and value.strip() and "CLAUDE_SESSION_ID" not in value:
        return value.strip()
    # Fallback: the most recently active session that has not ended.
    best, best_ts = None, ""
    for path in core.state_dir().glob("*.json"):
        state = core.read_json(path, default=None) or {}
        ts = state.get("last_checkpoint_ts") or ""
        if not state.get("ended_at") and ts > best_ts:
            best, best_ts = state.get("session_id"), ts
    return best


def cmd_hook(args) -> int:
    return collector.handle_hook(args.event, sys.stdin.read())


def cmd_flush(args) -> int:
    session_id = resolve_session(args.session)
    if not session_id:
        print("No session found to flush.", file=sys.stderr)
        return 1
    state = collector.load_state(session_id)
    cwd = state.get("cwd") or str(Path.cwd())
    payload = {
        "session_id": session_id,
        "cwd": cwd,
        "transcript_path": state.get("transcript_path") or transcript_guess(session_id, cwd),
    }
    collector.record("Manual", payload)
    created = summarizer.summarize_session(session_id)
    if not created:
        print(f"Nothing new to summarize for session {session_id}.")
        return 0
    for entry in created:
        print(f"[{entry['id']}] {entry['summary']} ({entry['status']})")
        for key in ("accomplished", "decisions", "blockers", "next_steps"):
            for item in entry.get(key) or []:
                print(f"  - {key}: {item}")
    print(f"Day view: {host_path(core.days_dir() / (created[-1]['date'] + '.md'))}")
    return 0


def cmd_summarize(args) -> int:
    if args.all:
        created = summarizer.summarize_all(workers=args.workers)
    elif args.session:
        created = summarizer.summarize_session(args.session)
    else:
        print("Pass --session ID or --all.", file=sys.stderr)
        return 2
    if args.quiet:
        return 0
    print(f"{len(created)} new entr{'y' if len(created) == 1 else 'ies'}.")
    for entry in created:
        print(f"[{entry['id']}] {entry['summary']}")
    return 0


def cmd_entries(args) -> int:
    since = parse_date(args.since) if args.since else core.last_workday(core.now().date())
    rows = views.entries(since, jira=args.jira)
    if args.format == "json":
        dump(rows)
    else:
        for day in sorted({r["date"] for r in rows}):
            print(views.render_day(day))
    return 0


def cmd_context(args) -> int:
    dump(views.context(parse_date(args.date)))
    return 0


def cmd_dates(args) -> int:
    today = parse_date(args.date)
    dump({
        "now": core.now_iso(),
        "today": today.isoformat(),
        "weekday": today.strftime("%A"),
        "tomorrow": (today + dt.timedelta(days=1)).isoformat(),
        "last_workday": core.last_workday(today).isoformat(),
        "timezone": str(core.now().tzinfo),
    })
    return 0


def cmd_meetings(args) -> int:
    day = parse_date(args.date).isoformat()
    files = sorted(
        p for p in core.meetings_dir().glob(f"*{day}*")
        if p.suffix.lower() in (".txt", ".md") and p.is_file()
    )
    dump([{"path": str(p), "host_path": host_path(p), "bytes": p.stat().st_size} for p in files])
    return 0


def cmd_github(args) -> int:
    dump(github.gather())
    return 0


def cmd_render_plan(args) -> int:
    path = Path(args.path)
    if not path.is_absolute() and not path.exists():
        path = core.home() / path
    html_path = plan.render_file(path)
    print(f"open {host_path(html_path)}")
    return 0


def cmd_init(args) -> int:
    root = core.ensure_home()
    print(f"Worklog ready in {root}")
    print(f"Config: {root / 'config.toml'}")
    return 0


def cmd_status(args) -> int:
    sessions = []
    for path in sorted(core.state_dir().glob("*.json")):
        state = core.read_json(path, default=None) or {}
        cursor = collector.load_cursor(state.get("session_id", path.stem))
        sessions.append({
            "session_id": state.get("session_id"),
            "repo": state.get("repo"),
            "worktree": state.get("worktree"),
            "branch": state.get("branch"),
            "jira": state.get("jira"),
            "last_checkpoint": state.get("last_checkpoint_ts"),
            "ended": bool(state.get("ended_at")),
            "pending_checkpoints": int(state.get("seq", 0)) - int(cursor["last_summarized_seq"]),
        })
    dump({"home": str(core.home()), "sessions": sessions})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worklog")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("hook", help="handle a Claude Code hook event (JSON on stdin)")
    p.add_argument("event")
    p.set_defaults(func=cmd_hook)

    p = sub.add_parser("flush", help="checkpoint and summarize a session now (/worklog)")
    p.add_argument("--session")
    p.set_defaults(func=cmd_flush)

    p = sub.add_parser("summarize", help="summarize unprocessed checkpoints")
    p.add_argument("--session")
    p.add_argument("--all", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_summarize)

    p = sub.add_parser("entries", help="query Worklog entries")
    p.add_argument("--since")
    p.add_argument("--jira")
    p.add_argument("--format", choices=("json", "md"), default="json")
    p.set_defaults(func=cmd_entries)

    p = sub.add_parser("context", help="Worklog context for the briefing")
    p.add_argument("--date")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("dates", help="today, tomorrow and last workday in the configured time zone")
    p.add_argument("--date")
    p.set_defaults(func=cmd_dates)

    p = sub.add_parser("meetings", help="meeting transcripts for a day")
    p.add_argument("--date")
    p.set_defaults(func=cmd_meetings)

    p = sub.add_parser("github", help="pull request data for the briefing")
    p.set_defaults(func=cmd_github)

    p = sub.add_parser("render-plan", help="render a plan JSON into HTML")
    p.add_argument("path")
    p.set_defaults(func=cmd_render_plan)

    p = sub.add_parser("init", help="create the Worklog directory, git repo and config")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status", help="sessions and their unprocessed checkpoints")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
