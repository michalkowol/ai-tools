"""Inbox capture state and the processing page.

State (`state/inbox.json`, written only by `worklog inbox …`):
  cursor  - start time of the last finished capture; Slack messages older than it are not captured again
  seen    - source URL -> capture time, a fast duplicate filter kept for REGISTRY_DAYS

The processing page (`inbox/YYYY-MM-DD-HHMM.json` -> `.html`) is declarative markup for the components in
`assets/` (`<inbox-app>`, `<inbox-entry>`, `<inbox-card>`), copied next to the page on every render. Every value
from Notion, Slack, GitHub or email is escaped plain text and only http(s) links are kept; the per-run HTML holds
content only, the look and behaviour live in the assets."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from . import core
from . import plan
from .plan import e, safe_url

REGISTRY_DAYS = 30
PAGE_FORMAT = "1"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ASSETS = ("inbox.css", "inbox-logic.js", "inbox-components.js")

OUTCOMES = ("done", "next", "today_candidates", "today", "calendar", "waiting", "agenda", "someday", "icebox", "trash",
            "keep")
CARD_ATTRS = ("outcome", "category", "estimate", "priority", "reminder", "due", "project", "agenda")


# ---------------------------------------------------------------- state

def inbox_dir() -> Path:
    return core.home() / "inbox"


def state_path() -> Path:
    return core.home() / "state" / "inbox.json"


def normalize_url(url: str) -> str:
    """Registry key: no trailing slash, lower-case scheme and host. Query and fragment stay: Slack thread
    permalinks and Gmail thread URLs differ only there."""
    url = (url or "").strip()
    parts = urlsplit(url)
    if not parts.scheme:
        return url
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, parts.fragment))


def load_state() -> dict[str, Any]:
    state = core.read_json(state_path(), default=None) or {}
    return {"cursor": state.get("cursor") or "", "seen": dict(state.get("seen") or {})}


def prune(seen: dict[str, str], now: dt.datetime) -> dict[str, str]:
    limit = now - dt.timedelta(days=REGISTRY_DAYS)
    kept = {}
    for url, ts in seen.items():
        try:
            if core.parse_ts(ts) >= limit:
                kept[url] = ts
        except (TypeError, ValueError):
            continue
    return kept


def start() -> dict[str, Any]:
    """Capture window: from the last cursor, or the start of the last workday on the first run."""
    now = core.now()
    state = load_state()
    if state["cursor"]:
        since = core.parse_ts(state["cursor"])
    else:
        day = core.last_workday(now.date())
        since = dt.datetime.combine(day, dt.time(0, 0), tzinfo=now.tzinfo)
    return {
        "since": since.isoformat(timespec="seconds"),
        "since_epoch": int(since.timestamp()),
        "since_date": since.date().isoformat(),
        "started_at": now.isoformat(timespec="seconds"),
        "first_run": not state["cursor"],
        "registry_size": len(prune(state["seen"], now)),
    }


def check(urls: list[str]) -> dict[str, list[str]]:
    seen = prune(load_state()["seen"], core.now())
    new, known = [], []
    for url in urls:
        (known if normalize_url(url) in seen else new).append(url)
    return {"new": list(dict.fromkeys(new)), "known": list(dict.fromkeys(known))}


def record(urls: list[str], cursor: str | None) -> dict[str, Any]:
    now = core.now()
    with core.file_lock("inbox"):
        state = load_state()
        seen = prune(state["seen"], now)
        stamp = now.isoformat(timespec="seconds")
        for url in urls:
            if url and url.strip():
                seen[normalize_url(url)] = stamp
        if cursor:
            core.parse_ts(cursor)  # validates the format
            state["cursor"] = cursor
        core.write_json_atomic(state_path(), {"cursor": state["cursor"], "seen": seen})
    return {"cursor": state["cursor"], "registry_size": len(seen), "recorded": len([u for u in urls if u])}


# ---------------------------------------------------------------- page

def _ts(value: Any) -> str:
    if not value:
        return ""
    try:
        return core.parse_ts(str(value)).isoformat()
    except ValueError:
        return ""


def order(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Two-minute entries first; inside both groups blocking others first, then entries whose first card has a due
    date (soonest first), then the rest, oldest first."""
    def key(entry: dict[str, Any]):
        cards = entry.get("cards") or [{}]
        due = (cards[0] or {}).get("due") or ""
        return (0 if entry.get("two_minute") else 1, 0 if entry.get("waiting_on_me") else 1, 0 if due else 1, due,
                _ts(entry.get("created_at")) or "9999")
    return sorted([x for x in entries if x and x.get("id")], key=key)


def _attrs(pairs: list[tuple[str, Any]]) -> str:
    out = []
    for name, value in pairs:
        if value is True:
            out.append(f" {name}")
        elif value not in (None, False, ""):
            out.append(f' {name}="{e(value)}"')
    return "".join(out)


def _category(value: Any) -> str:
    cats = set(value or ["Work"]) if isinstance(value, list) else {str(value)}
    if {"Work", "Home"} <= cats:
        return "Work+Home"
    return "Home" if "Home" in cats else "Work"


def _card(card: dict[str, Any], fallback_title: Any = "") -> str:
    outcome = card.get("outcome") if card.get("outcome") in OUTCOMES else "keep"
    attrs = [("outcome", outcome), ("category", _category(card.get("category")))]
    attrs += [(k, card.get(k)) for k in CARD_ATTRS[2:]]
    title = card.get("title") or fallback_title
    return f"    <inbox-card{_attrs(attrs)}>{e(title)}</inbox-card>\n"


def _entry(entry: dict[str, Any]) -> str:
    cards = [c for c in entry.get("cards") or [] if isinstance(c, dict)]
    if not cards:
        raise ValueError(f"entry {entry.get('id')!r} has no cards; the page JSON needs `cards` (format {PAGE_FORMAT})")
    src = entry.get("source") or {}
    head = _attrs([("entry-id", entry.get("id")), ("age", entry.get("age")), ("page-url", safe_url(entry.get("url"))),
                   ("waiting", bool(entry.get("waiting_on_me"))), ("result", entry.get("result"))])
    orig = _attrs([("href", safe_url(src.get("url"))), ("label", src.get("label"))]) if isinstance(src, dict) else ""
    why = f"    <inbox-why>{e(entry.get('why'))}</inbox-why>\n" if entry.get("why") else ""
    two = f"    <inbox-two-minute>{e(entry.get('two_minute'))}</inbox-two-minute>\n" if entry.get("two_minute") else ""
    return (
        f"  <inbox-entry{head}>\n"
        f"    <inbox-original{orig}>{e(entry.get('title'))}</inbox-original>\n"
        + "".join(_card(c, entry.get("title") if i == 0 else "") for i, c in enumerate(cards))
        + why
        + two
        + "  </inbox-entry>\n"
    )


def render(data: dict[str, Any], file_label: str) -> str:
    if "entries" not in data and "cards" in data:
        raise ValueError(f"old page JSON format (top-level `cards`); write `entries` (format {PAGE_FORMAT})")
    entries = order(data.get("entries") or [])
    cap = data.get("captured") or {}
    app = _attrs([("file", file_label), ("date", data.get("date")), ("generated-at", data.get("generated_at")),
                  ("captured", str(int(cap.get("created") or 0)) if cap else None),
                  ("skipped", str(int(cap.get("skipped") or 0)) if cap else None)])
    agenda = "".join(
        f"  <inbox-agenda{_attrs([('name', a.get('name'))])}></inbox-agenda>\n"
        for a in data.get("agenda_cards") or [] if isinstance(a, dict) and a.get("name")
    )
    missing = "".join(
        f"  <inbox-missing{_attrs([('source', m.get('source'))])}>{e(m.get('reason'))}</inbox-missing>\n"
        for m in data.get("missing_sources") or [] if isinstance(m, dict)
    )
    body = "".join(_entry(x) for x in entries)
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"<meta name=\"daily-workflow-inbox\" content=\"{PAGE_FORMAT}\">\n"
        f"<title>Inbox {e(data.get('date'))}</title>\n"
        "<link rel=\"stylesheet\" href=\"assets/inbox.css\">\n"
        "<script defer src=\"assets/inbox-logic.js\"></script>\n"
        "<script defer src=\"assets/inbox-components.js\"></script>\n"
        "</head>\n<body>\n"
        f"<inbox-app{app}>\n{agenda}{missing}{body}</inbox-app>\n"
        "</body>\n</html>\n"
    )


def copy_assets(target: Path) -> None:
    plan.copy_assets(ASSETS, target)


def render_file(json_path: Path, file_label: str) -> Path:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    page = render(data, file_label)
    copy_assets(json_path.parent / "assets")
    html_path = json_path.with_suffix(".html")
    tmp = html_path.with_name(f".{html_path.name}.tmp")
    tmp.write_text(page, encoding="utf-8")
    tmp.replace(html_path)
    return html_path
