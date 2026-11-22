"""Inbox capture state and the processing page.

State (`state/inbox.json`, written only by `worklog inbox …`):
  cursor  - start time of the last finished capture; Slack messages older than it are not captured again
  seen    - source URL -> capture time, a fast duplicate filter kept for REGISTRY_DAYS

The processing page (`inbox/YYYY-MM-DD-HHMM.json` -> `.html`) is a fixed template: every value from
Notion, Slack, GitHub or email is escaped, only http(s) links are kept, and the inline script only reads
form values and builds the prompt the user pastes back into the session."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from . import core
from .plan import e, link

REGISTRY_DAYS = 30

OUTCOMES = [
    ("done", "Done now"),
    ("next", "Next Actions"),
    ("waiting", "Waiting for"),
    ("agenda", "Agenda"),
    ("someday", "Someday/Maybe"),
    ("icebox", "Icebox"),
    ("trash", "Trash"),
    ("keep", "Keep in Inbox"),
]
OUTCOME_KEYS = {key for key, _ in OUTCOMES}
ESTIMATES = ["0.25 x 🍅", "0.5 x 🍅", "1 x 🍅", "2 x 🍅", "3 x 🍅", "4 x 🍅", "5 x 🍅", "6 x 🍅", "10 x 🍅", "None"]
PRIORITIES = ["P1", "P2", "P3"]
CATEGORIES = ["Work", "Home"]
FIELDS = ["title", "category", "estimate", "priority", "reminder", "due", "project", "agenda", "note"]


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

CSS = """
:root{--bg:#FAF9F5;--wash:#F0EEE6;--ink:#141413;--body:#3D3D3A;--muted:#87867F;--line:#D1CFC5;
--clay:#D97757;--olive:#788C5D;--oat:#E3DACC;--serif:Georgia,"Times New Roman",serif;
--sans:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;--mono:ui-monospace,Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--body);font:15px/1.5 var(--sans)}
main{max-width:900px;margin:0 auto;padding:32px 24px 80px}
.eyebrow{font:12px var(--mono);text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
h1{font:600 30px/1.2 var(--serif);color:var(--ink);margin:6px 0 8px}
.card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:14px 0}
.card.blocking{border-left:4px solid var(--clay)}
.card.decided-keep{opacity:.6}
.head{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.n{font:12px var(--mono);color:var(--muted)}
.t{font-weight:600;color:var(--ink)}a{color:var(--body)}
.src,.note,.why{color:var(--muted);font-size:13px}
blockquote{margin:8px 0;padding:4px 12px;border-left:3px solid var(--oat);color:var(--body)}
.k{display:inline-block;font:11px var(--mono);padding:1px 7px;border-radius:9px;background:var(--oat);color:var(--ink)}
.k.hot{background:var(--clay);color:#fff}.k.ok{background:var(--olive);color:#fff}
.outcomes{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 6px}
.outcomes label{border:1px solid var(--line);border-radius:14px;padding:2px 10px;cursor:pointer;font-size:13px}
.outcomes input{margin:0 4px 0 0}
.outcomes label.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.outcomes label.proposed::after{content:" ★";color:var(--clay)}
.fields{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px 12px;margin-top:6px}
.fields label{display:flex;flex-direction:column;font-size:12px;color:var(--muted);gap:2px}
.fields .wide{grid-column:1/-1}
input[type=text],input[type=date],select,textarea{font:14px var(--sans);padding:5px 7px;border:1px solid var(--line);
border-radius:5px;background:#fff;color:var(--body)}
.cats{display:flex;gap:10px;align-items:center;font-size:12px;color:var(--muted)}
.fields .cats label{flex-direction:row;align-items:center;gap:4px;font-size:13px;color:var(--body)}
[hidden]{display:none!important}
.bar{background:var(--wash);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin-top:24px}
.bar textarea{width:100%;height:120px;font:12px var(--mono)}
button{font:14px var(--sans);padding:6px 14px;border-radius:6px;border:1px solid var(--line);background:#fff;cursor:pointer}
button.primary{background:var(--ink);color:#fff;border-color:var(--ink)}
"""

# Fields shown per outcome. Everything not listed is hidden and left out of the prompt.
SHOWN = {
    "done": ["title", "category", "estimate", "priority", "project"],
    "next": ["title", "category", "estimate", "priority", "reminder", "due", "project"],
    "waiting": ["title", "category", "estimate", "priority", "reminder", "due", "project"],
    "agenda": ["agenda"],
    "someday": ["title", "category", "estimate", "priority", "project"],
    "icebox": ["title", "category", "estimate", "priority", "project"],
    "trash": [],
    "keep": [],
}

SCRIPT = """
(() => {
  const FILE = document.body.dataset.file;
  const KEY = 'daily-workflow:inbox:' + FILE;
  const SHOWN = JSON.parse(document.getElementById('shown').textContent);
  const FIELDS = JSON.parse(document.getElementById('fields').textContent);
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY)) || {}; } catch { saved = {}; }
  const cards = [...document.querySelectorAll('.card')];

  function read(card) {
    const out = { outcome: (card.querySelector('input[type=radio]:checked') || {}).value || 'keep' };
    for (const f of FIELDS) {
      if (f === 'category') {
        out.category = [...card.querySelectorAll('input[data-f=category]:checked')].map(i => i.value);
      } else {
        const el = card.querySelector('[data-f=' + f + ']');
        out[f] = el ? el.value.trim() : '';
      }
    }
    return out;
  }
  function write(card, v) {
    const r = card.querySelector('input[type=radio][value="' + v.outcome + '"]');
    if (r) r.checked = true;
    for (const f of FIELDS) {
      if (f === 'category') {
        card.querySelectorAll('input[data-f=category]').forEach(i => { i.checked = (v.category || []).includes(i.value); });
      } else {
        const el = card.querySelector('[data-f=' + f + ']');
        if (el && v[f] !== undefined) el.value = v[f];
      }
    }
  }
  function sync(card) {
    const v = read(card);
    const shown = SHOWN[v.outcome] || [];
    card.querySelectorAll('[data-field]').forEach(el => { el.hidden = !shown.includes(el.dataset.field); });
    card.querySelectorAll('.outcomes label').forEach(l => l.classList.toggle('on', l.querySelector('input').checked));
    card.classList.toggle('decided-keep', v.outcome === 'keep');
    const rem = card.querySelector('[data-field=reminder] span');
    if (rem) rem.textContent = v.outcome === 'waiting' ? 'Follow-up' : 'Reminder';
  }
  function prompt() {
    const lines = ['/daily-workflow:inbox apply ' + FILE];
    const state = {};
    let count = 0;
    for (const card of cards) {
      const v = read(card);
      state[card.dataset.id] = v;
      if (v.outcome === 'keep') continue;
      const shown = SHOWN[v.outcome] || [];
      const row = { id: card.dataset.id, outcome: v.outcome };
      for (const f of shown) row[f] = v[f];
      if (v.note) row.note = v.note;
      lines.push(JSON.stringify(row));
      count++;
    }
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* storage unavailable */ }
    document.getElementById('prompt').value = lines.join('\\n');
    document.getElementById('count').textContent = count + ' of ' + cards.length + ' cards processed';
  }
  for (const card of cards) {
    if (saved[card.dataset.id]) write(card, saved[card.dataset.id]);
    card.addEventListener('input', () => { sync(card); prompt(); });
    card.addEventListener('change', () => { sync(card); prompt(); });
    sync(card);
  }
  prompt();
  document.getElementById('copy').addEventListener('click', async (ev) => {
    const ta = document.getElementById('prompt');
    try { await navigator.clipboard.writeText(ta.value); } catch { ta.select(); document.execCommand('copy'); }
    ev.target.textContent = 'Copied';
    setTimeout(() => { ev.target.textContent = 'Copy'; }, 1500);
  });
  document.getElementById('reset').addEventListener('click', () => {
    try { localStorage.removeItem(KEY); } catch { /* storage unavailable */ }
    location.reload();
  });
})();
"""


def _ts(value: Any) -> str:
    if not value:
        return ""
    try:
        return core.parse_ts(str(value)).isoformat()
    except ValueError:
        return ""


def order(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Blocking others first, then cards with a due date (soonest first), then the rest, oldest first."""
    def key(card: dict[str, Any]):
        due = (card.get("proposal") or {}).get("due") or card.get("due") or ""
        return (0 if card.get("waiting_on_me") else 1, 0 if due else 1, due, _ts(card.get("created_at")) or "9999")
    return sorted([c for c in cards if c and c.get("id")], key=key)


def _options(values: list[str], selected: str, empty: str | None = "—") -> str:
    out = [f'<option value="">{e(empty)}</option>'] if empty is not None else []
    for v in values:
        out.append(f'<option value="{e(v)}"{" selected" if v == selected else ""}>{e(v)}</option>')
    return "".join(out)


def _card(i: int, card: dict[str, Any], projects: list[str], agenda: list[dict[str, Any]]) -> str:
    p = card.get("proposal") or {}
    outcome = p.get("outcome") if p.get("outcome") in OUTCOME_KEYS else "keep"
    cid = e(card.get("id"))
    src = card.get("source") or {}
    src_html = link(src.get("label") or "source", src.get("url")) if src else ""
    meta = " · ".join(x for x in (src_html, e(card.get("age"))) if x)
    title = link(card.get("title") or "(untitled)", card.get("url"))
    tags = []
    if card.get("waiting_on_me"):
        tags.append('<span class="k hot">someone is waiting</span>')
    if card.get("result"):
        tags.append(f'<span class="k ok">{e(card.get("result"))}</span>')
    quote = f"<blockquote>{e(card.get('quote'))}</blockquote>" if card.get("quote") else ""
    reason = f'<div class="why">{e(p.get("why"))}</div>' if p.get("why") else ""

    radios = "".join(
        f'<label class="{"proposed" if key == outcome else ""}"><input type="radio" name="o-{cid}" value="{key}"'
        f'{" checked" if key == outcome else ""}>{e(label)}</label>'
        for key, label in OUTCOMES
    )
    cats = p.get("category") or ["Work"]
    cat_boxes = "".join(
        f'<label><input type="checkbox" data-f="category" value="{c}"{" checked" if c in cats else ""}> {c}</label>'
        for c in CATEGORIES
    )
    agenda_names = [a.get("name") for a in agenda if a and a.get("name")]
    fields = (
        f'<label class="wide" data-field="title">Title<input type="text" data-f="title" value="{e(p.get("title") or card.get("title"))}"></label>'
        f'<div data-field="category" class="cats">Category {cat_boxes}</div>'
        f'<label data-field="estimate">Estimate<select data-f="estimate">{_options(ESTIMATES, p.get("estimate") or "")}</select></label>'
        f'<label data-field="priority">Priority<select data-f="priority">{_options(PRIORITIES, p.get("priority") or "")}</select></label>'
        f'<label data-field="reminder"><span>Reminder</span><input type="date" data-f="reminder" value="{e(p.get("reminder"))}"></label>'
        f'<label data-field="due">Due Date<input type="date" data-f="due" value="{e(p.get("due"))}"></label>'
        f'<label data-field="project">Project<select data-f="project">{_options(projects, p.get("project") or "")}</select></label>'
        f'<label data-field="agenda">Agenda card<select data-f="agenda">{_options(agenda_names, p.get("agenda") or "")}</select></label>'
        f'<label class="wide">Note<input type="text" data-f="note" value=""></label>'
    )
    return (
        f'<div class="card{" blocking" if card.get("waiting_on_me") else ""}" data-id="{cid}">'
        f'<div class="head"><span class="n">{i}</span><span class="t">{title}</span>{"".join(tags)}</div>'
        f'<div class="src">{meta}</div>{quote}{reason}'
        f'<div class="outcomes">{radios}</div><div class="fields">{fields}</div></div>'
    )


def _json_script(element_id: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/json" id="{element_id}">{payload}</script>'


def render(data: dict[str, Any], file_label: str) -> str:
    cards = order(data.get("cards") or [])
    projects = [p for p in data.get("projects") or [] if isinstance(p, str) and p]
    agenda = [a for a in data.get("agenda_cards") or [] if isinstance(a, dict)]
    cap = data.get("captured") or {}
    summary = []
    if cap:
        summary.append(f"{int(cap.get('created') or 0)} new cards captured, {int(cap.get('skipped') or 0)} duplicates skipped")
    summary.append(f"{len(cards)} cards in the Inbox")
    missing = data.get("missing_sources") or []
    missing_html = (
        '<p class="note">Missing sources: '
        + "; ".join(f"{e(m.get('source'))} ({e(m.get('reason'))})" for m in missing if isinstance(m, dict))
        + "</p>"
    ) if missing else ""
    body = "".join(_card(i + 1, c, projects, agenda) for i, c in enumerate(cards))
    if not cards:
        body = '<p class="note">Inbox zero.</p>'
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        f"<title>Inbox {e(data.get('date'))}</title><style>{CSS}</style></head>"
        f'<body data-file="{e(file_label)}"><main>'
        f'<div class="eyebrow">{e(data.get("date"))} · inbox processing</div><h1>Inbox</h1>'
        f'<p class="note">{e(" · ".join(summary))}. ★ marks the proposal. Pick an outcome, adjust the fields, copy the prompt into the session.</p>'
        f"{missing_html}{body}"
        '<div class="bar"><div class="head"><span class="t">Prompt</span><span class="note" id="count"></span></div>'
        '<textarea id="prompt" readonly></textarea>'
        '<div class="head"><button class="primary" id="copy" type="button">Copy</button>'
        '<button id="reset" type="button">Reset answers</button></div></div>'
        f'<p class="note">Generated {e(data.get("generated_at"))}</p></main>'
        f"{_json_script('shown', SHOWN)}{_json_script('fields', FIELDS)}"
        f"<script>{SCRIPT}</script></body></html>\n"
    )


def render_file(json_path: Path, file_label: str) -> Path:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    html_path = json_path.with_suffix(".html")
    tmp = html_path.with_name(f".{html_path.name}.tmp")
    tmp.write_text(render(data, file_label), encoding="utf-8")
    tmp.replace(html_path)
    return html_path

