#!/usr/bin/env python3
"""Worklog CLI: hook handler, summarizer, queries and plan rendering.

Usage (the most common ones):
  worklog.py hook <Event>                 # called by Claude Code hooks, JSON on stdin
  worklog.py flush [--session ID]         # /worklog: checkpoint + summary now
  worklog.py summarize --all              # catch-up of every unprocessed session
  worklog.py context                      # Worklog context for the day plan (JSON)
  worklog.py github                       # pull request data for the day plan (JSON)
  worklog.py render-plan plans/2026-11-23.json
  worklog.py plan-apply plans/2026-11-23.json < pasted-lines  # ticks, notes for AI and list order from the plan page
  worklog.py plan-result plans/2026-11-23.json < result-lines # what became of the notes for AI
  worklog.py inbox start|check|record       # inbox capture state (JSON)
  worklog.py render-inbox inbox/2026-11-23-0930.json
  worklog.py knowledge start|files|check|add|record  # local knowledge base (md files) from Slack to-dos and channels
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wl import collector, core, github, inbox, knowledge, plan, summarizer, views  # noqa: E402


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


def plan_path(arg: str) -> tuple[Path, str]:
    path = Path(arg)
    if not path.is_absolute() and not path.exists():
        path = core.home() / path
    path = path.resolve()
    try:
        label = str(path.relative_to(core.home().resolve()))
    except ValueError:
        label = str(path)
    return path, label


def cmd_render_plan(args) -> int:
    path, label = plan_path(args.path)
    html_path = plan.render_file(path, label)
    print(f"open {host_path(html_path)}")
    return 0


def read_json_lines() -> list[dict]:
    """The JSON object lines on stdin; the prompt header and anything else is skipped."""
    out = []
    for line in sys.stdin.read().splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def cmd_plan_apply(args) -> int:
    """Lines pasted from the plan page ("Copy prompt") on stdin: mark the ticked items done, store the notes for AI,
    apply the order of the rearranged lists in the JSON and re-render."""
    path, label = plan_path(args.path)
    lines = [line for line in read_json_lines() if line.get("key") or line.get("order")]
    data = json.loads(path.read_text(encoding="utf-8"))
    result = plan.apply_lines(data, lines, core.now_iso())
    core.write_json_atomic(path, data)
    result["open"] = f"open {host_path(plan.render_file(path, label))}"
    dump(result)
    return 0


def cmd_plan_result(args) -> int:
    """What became of the notes for AI, one {"id": 1, "result": "applied: …"} line each on stdin: store the results
    in the JSON and re-render."""
    path, label = plan_path(args.path)
    data = json.loads(path.read_text(encoding="utf-8"))
    result = plan.set_results(data, [line for line in read_json_lines() if "id" in line])
    core.write_json_atomic(path, data)
    result["open"] = f"open {host_path(plan.render_file(path, label))}"
    dump(result)
    return 0


def read_list(values: list[str]) -> list[str]:
    """The arguments, or a JSON list on stdin when there are none."""
    if values:
        return values
    if sys.stdin.isatty():
        return []
    raw = sys.stdin.read().strip()
    data = json.loads(raw) if raw else []
    if not isinstance(data, list):
        raise SystemExit("expected a JSON list on stdin")
    return [str(u) for u in data if u]


def cmd_inbox(args) -> int:
    core.ensure_home()
    if args.action == "start":
        dump(inbox.start())
    elif args.action == "check":
        dump(inbox.check(read_list(args.urls)))
    else:
        dump(inbox.record(read_list(args.urls), args.cursor))
    return 0


def cmd_knowledge(args) -> int:
    """The knowledge base: `start` (files and channel windows), `files`, `check` (source URLs already in the
    base), `add` (file and entry lines on stdin), `record` (move the window of the channels that were read)."""
    core.ensure_home()
    if args.action == "start":
        data = knowledge.start(args.days)
    elif args.action == "files":
        data = {"dir": str(knowledge.base_dir()), "files": knowledge.files()}
    elif args.action == "check":
        data = knowledge.check(read_list(args.items))
    elif args.action == "add":
        data = knowledge.add(read_json_lines())
    else:
        if not args.cursor:
            print("[knowledge] record needs --cursor <started_at>", file=sys.stderr)
            return 2
        data = knowledge.record(args.cursor, read_list(args.items))
    data["open"] = f"open {host_path(knowledge.base_dir())}"
    dump(data)
    return 0


def cmd_render_inbox(args) -> int:
    path = Path(args.path)
    if not path.is_absolute() and not path.exists():
        path = core.home() / path
    path = path.resolve()
    try:
        label = str(path.relative_to(core.home().resolve()))
    except ValueError:
        label = str(path)
    try:
        html_path = inbox.render_file(path, label)
    except ValueError as exc:
        print(f"[render-inbox] {exc}", file=sys.stderr)
        return 1
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

    p = sub.add_parser("context", help="Worklog context for the day plan")
    p.add_argument("--date")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("dates", help="today, tomorrow and last workday in the configured time zone")
    p.add_argument("--date")
    p.set_defaults(func=cmd_dates)

    p = sub.add_parser("meetings", help="meeting transcripts for a day")
    p.add_argument("--date")
    p.set_defaults(func=cmd_meetings)

    p = sub.add_parser("github", help="pull request data for the day plan")
    p.set_defaults(func=cmd_github)

    p = sub.add_parser("render-plan", help="render a plan JSON into HTML")
    p.add_argument("path")
    p.set_defaults(func=cmd_render_plan)

    p = sub.add_parser("plan-apply", help="apply the ticks, notes for AI and list order from the plan page (prompt lines on stdin)")
    p.add_argument("path")
    p.set_defaults(func=cmd_plan_apply)

    p = sub.add_parser("plan-result", help="store the results of the notes for AI (id and result lines on stdin)")
    p.add_argument("path")
    p.set_defaults(func=cmd_plan_result)

    p = sub.add_parser("inbox", help="inbox capture state: window, duplicate check, record")
    p.add_argument("action", choices=("start", "check", "record"))
    p.add_argument("urls", nargs="*", help="source URLs (or a JSON list on stdin)")
    p.add_argument("--cursor", help="record: the started_at of this capture")
    p.set_defaults(func=cmd_inbox)

    p = sub.add_parser("knowledge", help="knowledge base: files, channel windows, duplicate check, add, record")
    p.add_argument("action", choices=("start", "files", "check", "add", "record"))
    p.add_argument("items", nargs="*", help="check: source URLs; record: the channels that were read "
                                            "(or a JSON list on stdin)")
    p.add_argument("--days", type=int, help="start: days to read from a channel the first time (default 30)")
    p.add_argument("--cursor", help="record: the started_at of this run")
    p.set_defaults(func=cmd_knowledge)

    p = sub.add_parser("render-inbox", help="render an inbox JSON into the processing page")
    p.add_argument("path")
    p.set_defaults(func=cmd_render_inbox)

    p = sub.add_parser("init", help="create the Worklog directory, git repo and config")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status", help="sessions and their unprocessed checkpoints")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
