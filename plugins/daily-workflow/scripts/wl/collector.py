"""Hook handler: writes Technical Checkpoints without any LLM call."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import core

MAX_PROMPT_CHARS = 1500
MAX_REPLY_CHARS = 3000
MAX_PROMPTS = 6

# PostToolUse signals detected from Bash commands. Order matters only for display.
BASH_SIGNALS = [
    ("git_commit", re.compile(r"\bgit\s+(?:-\S+\s+)*commit\b")),
    ("git_push", re.compile(r"\bgit\s+(?:-\S+\s+)*push\b")),
    ("pr_created", re.compile(r"\bgh\s+pr\s+create\b")),
    ("pr_merged", re.compile(r"\bgh\s+pr\s+merge\b")),
    ("pr_reviewed", re.compile(r"\bgh\s+pr\s+review\b")),
    (
        "tests_run",
        re.compile(
            r"\b(?:pytest|jest|vitest|rspec|phpunit|tox|go\s+test|cargo\s+test|"
            r"(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test|make\s+test|"
            r"(?:mvn|mvnw|\./mvnw)\b[^|;&]*\b(?:test|verify)|"
            r"(?:gradle|gradlew|\./gradlew)\b[^|;&]*\b(?:test|check|build))\b"
        ),
    ),
]

# PostToolUse signals detected from MCP tool names (lower-cased substring match).
MCP_SIGNALS = [
    ("jira_transition", "transitionjiraissue"),
    ("jira_created", "createjiraissue"),
    ("jira_comment", "jiraissuecomment"),
    ("jira_edited", "editjiraissue"),
    ("pr_created", "create_pull_request"),
    ("pr_merged", "merge_pull_request"),
]


def git_meta(cwd: str) -> dict[str, Any]:
    """Repo, worktree and git state. In the Docker sandbox cwd is always
    /workspace, so names come from git, not from the directory."""
    top = core.git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return {"repo": None, "worktree": None, "branch": None, "git": None}
    git_dir = core.git(cwd, "rev-parse", "--absolute-git-dir") or ""
    common = core.git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir") or ""
    worktree = Path(git_dir).name if "/worktrees/" in git_dir else None

    repo = None
    remote = core.git(cwd, "remote", "get-url", "origin")
    if remote:
        repo = re.sub(r"\.git$", "", remote.rstrip("/").split("/")[-1].split(":")[-1]) or None
    if not repo and common:
        parent = Path(common).parent.name if Path(common).name == ".git" else Path(common).name
        repo = re.sub(r"\.git$", "", parent) or None
    if not repo:
        repo = Path(top).name

    branch = core.git(cwd, "branch", "--show-current") or None
    head = core.git(cwd, "rev-parse", "--short", "HEAD")
    porcelain = core.git(cwd, "status", "--porcelain", timeout=10)
    shortstat = core.git(cwd, "diff", "--shortstat", "HEAD", timeout=10) or ""
    ins = re.search(r"(\d+) insertion", shortstat)
    dels = re.search(r"(\d+) deletion", shortstat)
    diffstat = f"+{ins.group(1) if ins else 0} -{dels.group(1) if dels else 0}" if shortstat else ""
    return {
        "repo": repo,
        "worktree": worktree,
        "branch": branch,
        "git": {
            "head": head,
            "dirty_files": len(porcelain.splitlines()) if porcelain else 0,
            "diffstat": diffstat,
        },
    }


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p)
    return ""


def read_turns(transcript: str | None, start: int, end: int) -> tuple[list[str], str]:
    """Best-effort read of user prompts and the last assistant text in a byte
    range of the transcript. The format is internal to Claude Code, so any
    parsing problem just returns what was found so far."""
    prompts: list[str] = []
    last_reply = ""
    if not transcript or end <= start:
        return prompts, last_reply
    try:
        with open(transcript, "rb") as fh:
            fh.seek(start)
            chunk = fh.read(end - start)
    except OSError:
        return prompts, last_reply
    for raw in chunk.splitlines():
        try:
            row = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(row, dict) or row.get("isMeta") or row.get("isSidechain"):
            continue
        message = row.get("message") or {}
        if row.get("type") == "user" and message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, list) and any(
                isinstance(i, dict) and i.get("type") == "tool_result" for i in content
            ):
                continue
            text = _text_of(content).strip()
            if text and not text.startswith(("<local-command", "<system-reminder")):
                prompts.append(core.truncate(text, MAX_PROMPT_CHARS))
        elif row.get("type") == "assistant":
            text = _text_of(message.get("content")).strip()
            if text:
                last_reply = text
    return prompts[-MAX_PROMPTS:], core.truncate(last_reply, MAX_REPLY_CHARS)


def detect_signals(payload: dict[str, Any]) -> tuple[list[str], str]:
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        signals = [name for name, rx in BASH_SIGNALS if rx.search(command)]
        return signals, core.truncate(command, 300)
    lowered = tool.lower()
    signals = [name for name, needle in MCP_SIGNALS if needle in lowered]
    issue = tool_input.get("issueIdOrKey") or tool_input.get("issueKey") or ""
    return signals, f"{tool} {issue}".strip()


def load_state(session_id: str) -> dict[str, Any]:
    return core.read_json(core.state_dir() / f"{session_id}.json", default=None) or {
        "session_id": session_id,
        "source": "claude-code",
        "seq": 0,
        "transcript_offset": 0,
        "started_at": core.now_iso(),
        "checkpoint_days": [],
    }


def save_state(state: dict[str, Any]) -> None:
    core.write_json_atomic(core.state_dir() / f"{state['session_id']}.json", state)


def spawn_summarizer(session_id: str) -> None:
    script = core.PLUGIN_ROOT / "scripts" / "worklog.py"
    env = dict(os.environ, WORKLOG_DISABLE="1")
    try:
        core.logs_dir().mkdir(parents=True, exist_ok=True)
        log_fh = open(core.logs_dir() / "summarizer.log", "a")
        subprocess.Popen(
            [sys.executable, str(script), "summarize", "--session", session_id],
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=log_fh,
            start_new_session=True,
            env=env,
        )
    except OSError as exc:
        core.log(f"[collector] could not start the summarizer for {session_id}: {exc}")


def load_cursor(session_id: str) -> dict[str, Any]:
    """Summary cursor. Kept apart from the session state because the summarizer
    may run in another container (briefing catch-up) than the session hooks."""
    return core.read_json(core.cursors_dir() / f"{session_id}.json", default=None) or {
        "session_id": session_id,
        "last_summarized_seq": 0,
        "last_summary_ts": None,
    }


def summary_due(state: dict[str, Any]) -> bool:
    cursor = load_cursor(state["session_id"])
    if state["seq"] <= cursor["last_summarized_seq"]:
        return False
    reference = cursor.get("last_summary_ts") or state.get("started_at")
    if not reference:
        return True
    minutes = float(core.config()["worklog"].get("summary_threshold_minutes", 15))
    elapsed = (core.now() - core.parse_ts(reference)).total_seconds() / 60
    return elapsed >= minutes


def record(event: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Write one checkpoint for a hook event. Returns the checkpoint, or None
    when there was nothing worth recording."""
    session_id = payload.get("session_id")
    if not session_id:
        return None
    cwd = payload.get("cwd") or os.getcwd()
    signals: list[str] = []
    detail = ""
    if event == "PostToolUse":
        signals, detail = detect_signals(payload)
        if not signals:
            return None

    core.ensure_home()
    meta = git_meta(cwd)
    with core.file_lock(f"session-{session_id}") as locked:
        if not locked:
            core.log(f"[collector] session lock busy, {event} for {session_id} skipped")
            return None
        state = load_state(session_id)
        transcript = payload.get("transcript_path") or state.get("transcript_path")
        checkpoint: dict[str, Any] = {
            "v": 1,
            "source": "claude-code",
            "event": event,
            "ts": core.now_iso(),
            "session_id": session_id,
            "cwd": cwd,
            "repo": meta["repo"],
            "worktree": meta["worktree"],
            "branch": meta["branch"],
            "jira": core.find_jira_key(meta["branch"], meta["worktree"]),
            "git": meta["git"],
        }
        if event in ("Stop", "PreCompact", "SessionEnd", "Manual"):
            start = int(state.get("transcript_offset") or 0)
            end = start
            if transcript:
                try:
                    end = os.path.getsize(transcript)
                except OSError:
                    end = start
            if end < start:  # transcript replaced, start over
                start = 0
            prompts, reply = read_turns(transcript, start, end)
            if event == "Stop" and payload.get("last_assistant_message"):
                reply = core.truncate(payload["last_assistant_message"], MAX_REPLY_CHARS)
            checkpoint["transcript"] = {"path": transcript, "from": start, "to": end}
            checkpoint["prompts"] = prompts
            checkpoint["reply"] = reply
            state["transcript_offset"] = end
        if event == "SessionStart":
            checkpoint["start_source"] = payload.get("source")
        if event == "SessionEnd":
            checkpoint["reason"] = payload.get("reason")
            state["ended_at"] = checkpoint["ts"]
        if event == "PreCompact":
            checkpoint["trigger"] = payload.get("trigger")
        if signals:
            checkpoint["signals"] = signals
            checkpoint["detail"] = detail

        state["seq"] += 1
        checkpoint["seq"] = state["seq"]
        day = core.parse_ts(checkpoint["ts"]).date().isoformat()
        core.append_jsonl(core.checkpoints_dir() / day / f"{session_id}.jsonl", checkpoint)
        if day not in state["checkpoint_days"]:
            state["checkpoint_days"].append(day)
        state.update(
            cwd=cwd,
            transcript_path=transcript,
            repo=meta["repo"] or state.get("repo"),
            worktree=meta["worktree"] or state.get("worktree"),
            branch=meta["branch"] or state.get("branch"),
            jira=checkpoint["jira"] or state.get("jira"),
            last_checkpoint_ts=checkpoint["ts"],
        )
        save_state(state)
    return checkpoint


def handle_hook(event: str, stdin_text: str) -> int:
    """Entry point for hooks. Never fails the hook: errors go to the log."""
    if os.environ.get("WORKLOG_DISABLE"):
        return 0
    try:
        payload = json.loads(stdin_text or "{}")
    except json.JSONDecodeError:
        core.log(f"[collector] invalid hook input for {event}")
        return 0
    try:
        checkpoint = record(event, payload)
        if not checkpoint:
            return 0
        session_id = checkpoint["session_id"]
        if event == "PreCompact":
            spawn_summarizer(session_id)
        elif event == "Stop" and summary_due(load_state(session_id)):
            spawn_summarizer(session_id)
        # SessionEnd only records the checkpoint: the container stops with the
        # session, so a background summary would be killed.
    except Exception as exc:  # a hook must never break the session
        core.log(f"[collector] {event} failed: {exc!r}")
    return 0
