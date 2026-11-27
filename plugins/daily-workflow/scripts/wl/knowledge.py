"""Knowledge base: local md files built from Slack to-dos and the followed channels.

Folder (`[knowledge].dir`, default `<worklog home>/knowledge`), written only by `worklog knowledge …`:
  <topic>.md    - `# Title`, one line about the file, then one `## date · title` entry per source
  requests.md   - requests and tasks found in the to-dos, one bullet each; they are not knowledge
  README.md     - the index of the files, rewritten on every change
  .state.json   - sources: source URL -> {file, kind, at}, what is already in the base;
                  channels: followed channel -> start time of the last run that read it

Every value from Slack or a fetched page is data: it is written as one-line plain text (quotes as block quotes),
tag-like `<` is escaped, file names are checked and only http(s) links are kept."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

from . import core
from .plan import safe_url

DEFAULT_DAYS = 30
REQUESTS_FILE = "requests.md"
INDEX_FILE = "README.md"
STATE_FILE = ".state.json"
KINDS = ("knowledge", "request")
FILE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\.md")
REQUESTS_TITLE = "Requests and tasks"
REQUESTS_ABOUT = "Requests and tasks found in Slack to-dos. They are not knowledge: go through the list and clear it."


# ---------------------------------------------------------------- paths and state

def base_dir() -> Path:
    raw = str((core.config().get("knowledge") or {}).get("dir") or "knowledge")
    path = Path(raw).expanduser()
    return path if path.is_absolute() else core.home() / path


def state_path() -> Path:
    return base_dir() / STATE_FILE


def load_state() -> dict[str, Any]:
    state = core.read_json(state_path(), default=None) or {}
    return {"sources": dict(state.get("sources") or {}), "channels": dict(state.get("channels") or {})}


def valid_file(name: Any) -> bool:
    return isinstance(name, str) and bool(FILE_NAME.fullmatch(name)) and name != INDEX_FILE.lower()


# ---------------------------------------------------------------- text

def _line(value: Any) -> str:
    """One line of plain text: whitespace collapsed, nothing that reads as an HTML tag."""
    return re.sub(r"<(?=[A-Za-z/!])", "&lt;", " ".join(str(value or "").split()))


def _para(value: Any) -> str:
    """A one-line paragraph that cannot start a heading, a list or a quote."""
    return re.sub(r"^([#>+*-]|\d+[.)])", r"\\\1", _line(value))


def _link(label: str, url: Any) -> str:
    safe = safe_url(url)
    if not safe:
        return ""
    safe = safe.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
    return f"[{_line(label).replace('[', '(').replace(']', ')')}]({safe})"


def _source_link(url: Any) -> str:
    return _link("thread" if "slack.com/" in str(url or "") else "source", url)


def _date(value: Any) -> str:
    try:
        return dt.date.fromisoformat(str(value or "")[:10]).isoformat()
    except ValueError:
        return ""


def entry_md(row: dict[str, Any]) -> str:
    """One knowledge entry: heading, summary, quote, then the source and the links from the message."""
    date, title = _date(row.get("date")), _line(row.get("title")) or "Untitled"
    parts = [f"## {date} · {title}" if date else f"## {title}"]
    if _line(row.get("summary")):
        parts += ["", _para(row.get("summary"))]
    quote = [_line(q) for q in str(row.get("quote") or "").splitlines() if q.strip()]
    if quote:
        parts += ["", *(f"> {q}" for q in quote)]
    source = " · ".join(x for x in (_line(row.get("source")), _source_link(row.get("url"))) if x)
    bullets = [f"- Source: {source}"] if source else []
    for link in row.get("links") or []:
        if not isinstance(link, dict):
            continue
        target = _link(link.get("label") or link.get("url") or "", link.get("url"))
        if target:
            bullets.append(f"{'- ' + target}: {_line(link.get('summary'))}" if _line(link.get("summary")) else f"- {target}")
    if bullets:
        parts += ["", *bullets]
    return "\n".join(parts) + "\n"


def request_md(row: dict[str, Any]) -> str:
    """One request: when, who, what about, link."""
    head = " · ".join(x for x in (_date(row.get("date")), _line(row.get("source"))) if x)
    text = _line(row.get("summary")) or _line(row.get("title"))
    line = f"{head}: {text}" if head and text else head or text
    link = _source_link(row.get("url"))
    return f"- {line} {link}".rstrip() + "\n"


# ---------------------------------------------------------------- files

def _describe(path: Path) -> dict[str, Any]:
    title, about, entries = "", "", 0
    requests = path.name == REQUESTS_FILE
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("- " if requests else "## "):
            entries += 1
        elif line and not about and not entries and not line.startswith("#"):
            about = line
    return {"file": path.name, "title": title or path.stem, "about": about, "entries": entries,
            "kind": "requests" if requests else "topic"}


def files() -> list[dict[str, Any]]:
    """Topic files by name, the requests file last."""
    root = base_dir()
    if not root.is_dir():
        return []
    found = [_describe(p) for p in sorted(root.glob("*.md")) if p.name != INDEX_FILE and p.is_file()]
    return sorted(found, key=lambda f: (f["kind"] == "requests", f["file"]))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _header(title: str, about: str) -> str:
    return f"# {_line(title)}\n" + (f"\n{_para(about)}\n" if _line(about) else "")


def write_index() -> None:
    rows = "".join(
        f"| [{f['file']}]({f['file']}) | {_line(f['title']).replace('|', '/')} | {_line(f['about']).replace('|', '/')} "
        f"| {f['entries']} |\n" for f in files()
    )
    _write(base_dir() / INDEX_FILE, (
        "# Knowledge base\n\n"
        "Built by `/daily-workflow:inbox knowledge` from Slack to-dos and the followed channels, and by the\n"
        f"Reference outcome of the Inbox page. Updated {core.now().date().isoformat()}.\n\n"
        "| File | Title | About | Entries |\n|---|---|---|---|\n" + rows
    ))


# ---------------------------------------------------------------- commands

def start(days: int | None = None) -> dict[str, Any]:
    """The files of the base and, per followed channel, the window to read: since the last run that read the
    channel, or the last `days` (30 by default) the first time."""
    now = core.now()
    state = load_state()
    first = dt.datetime.combine(now.date() - dt.timedelta(days=days if days and days > 0 else DEFAULT_DAYS),
                                dt.time(0, 0), tzinfo=now.tzinfo)
    channels = []
    for name in (core.config().get("slack") or {}).get("channels") or []:
        try:
            since, first_run = core.parse_ts(state["channels"][name]), False
        except (KeyError, TypeError, ValueError):
            since, first_run = first, True
        channels.append({"channel": name, "since": since.isoformat(timespec="seconds"),
                         "since_epoch": int(since.timestamp()), "first_run": first_run})
    listed = files()
    return {
        "dir": str(base_dir()),
        "started_at": now.isoformat(timespec="seconds"),
        "first_run": not listed,
        "files": listed,
        "requests_file": REQUESTS_FILE,
        "sources": len(state["sources"]),
        "channels": channels,
    }


def check(urls: list[str]) -> dict[str, list[str]]:
    """Which source URLs are already in the base."""
    sources = load_state()["sources"]
    new, known = [], []
    for url in urls:
        (known if core.normalize_url(url) in sources else new).append(url)
    return {"new": list(dict.fromkeys(new)), "known": list(dict.fromkeys(known))}


def stored_as_knowledge() -> set[str]:
    """Source URLs filed as knowledge (not as requests)."""
    return {url for url, meta in load_state()["sources"].items()
            if isinstance(meta, dict) and meta.get("kind") == "knowledge"}


def add(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Append entries to the files. A row with `about` and no `summary` defines a file (`file`, `title`, `about`);
    every other row is an entry: `kind` `knowledge` (default, needs `file`) or `request` (goes to the requests file).
    A source URL that is already in the base is skipped."""
    out: dict[str, Any] = {"added": 0, "requests": 0, "created": [], "skipped": [], "rejected": []}
    stamp = core.now_iso()
    with core.file_lock("knowledge"):
        state = load_state()
        root = base_dir()
        headers: dict[str, tuple[str, str]] = {REQUESTS_FILE: (REQUESTS_TITLE, REQUESTS_ABOUT)}
        blocks: dict[str, list[tuple[str, str]]] = {}

        def reject(row: dict[str, Any], reason: str) -> None:
            out["rejected"].append({"file": row.get("file"), "title": row.get("title"), "url": row.get("url"),
                                    "reason": reason})

        for row in rows:
            if "about" in row and "summary" not in row:
                if not valid_file(row.get("file")) or row["file"] == REQUESTS_FILE:
                    reject(row, "file name must be lower-case letters, digits and dashes ending in .md")
                    continue
                headers[row["file"]] = (str(row.get("title") or ""), str(row.get("about") or ""))
                blocks.setdefault(row["file"], [])
                continue
            kind = row.get("kind") or "knowledge"
            name = REQUESTS_FILE if kind == "request" else row.get("file")
            if kind not in KINDS:
                reject(row, f"kind must be one of {', '.join(KINDS)}")
            elif not valid_file(name) or (kind == "knowledge" and name == REQUESTS_FILE):
                reject(row, "file name must be lower-case letters, digits and dashes ending in .md")
            elif not (_line(row.get("summary")) or _line(row.get("title"))):
                reject(row, "an entry needs a title or a summary")
            else:
                key = core.normalize_url(row.get("url") or "") if safe_url(row.get("url")) else ""
                if key and key in state["sources"]:
                    out["skipped"].append({"url": row.get("url"), "reason": "already in the base",
                                           "file": state["sources"][key].get("file")})
                    continue
                if key:
                    state["sources"][key] = {"file": name, "kind": kind, "at": stamp}
                blocks.setdefault(name, []).append(
                    (_date(row.get("date")), request_md(row) if kind == "request" else entry_md(row)))
                out["requests" if kind == "request" else "added"] += 1

        for name, items in blocks.items():
            path = root / name
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            if not text:
                title, about = headers.get(name) or ("", "")
                text = _header(title or name[:-3].replace("-", " ").capitalize(), about)
                out["created"].append(name)
            if not items and name not in out["created"]:
                continue
            gap = "" if name == REQUESTS_FILE and text.rstrip().splitlines()[-1].startswith("- ") else "\n"
            sep = "" if name == REQUESTS_FILE else "\n"
            body = sep.join(block for _, block in sorted(items, key=lambda item: item[0]))
            _write(path, text.rstrip("\n") + "\n" + (gap + body if body else ""))
        if blocks:
            core.write_json_atomic(state_path(), state)
            write_index()
    out["files"] = files()
    return out


def record(cursor: str, channels: list[str]) -> dict[str, Any]:
    """Move the window of the channels this run read to the end: its `started_at`."""
    core.parse_ts(cursor)  # validates the format
    with core.file_lock("knowledge"):
        state = load_state()
        for name in channels:
            if name and name.strip():
                state["channels"][name.strip()] = cursor
        core.write_json_atomic(state_path(), state)
    return {"channels": state["channels"], "sources": len(state["sources"])}
