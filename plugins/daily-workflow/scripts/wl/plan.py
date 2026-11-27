"""Renders plans/YYYY-MM-DD[-home].json into a fixed HTML page.

Every value is escaped and only http(s) links are kept: the plan holds text
gathered from email, Slack and transcripts, which is data, never markup.

The page is light DOM custom elements with the content inside (readable without JS):
<plan-page file> holds the header and <main>, every section is a <plan-section name>, every item a
<plan-item key label [url] [done]>. `assets/plan.js` adds the checkboxes, the section counters and the "Copy done"
bar. The key is section + URL, or the text when there is no URL, so ticks kept in localStorage survive a re-render.
`mark_done` writes ticks pasted back from the page into the JSON: `done: true` on object items, the key in
`done_items` for plain-text items."""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

from . import core

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ASSETS = ("plan.css", "plan.js")
PAGE_FORMAT = "2"

KIND_LABEL = {"deep": "deep focus", "heavy": "heavy", "light": "light"}


def e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def safe_url(url: Any) -> str | None:
    if isinstance(url, str) and url.startswith(("https://", "http://")):
        return url
    return None


def link(text: Any, url: Any) -> str:
    href = safe_url(url)
    return f'<a href="{e(href)}">{e(text)}</a>' if href else e(text)


def source(src: Any) -> str:
    if not src:
        return ""
    if isinstance(src, str):
        return f' <span class="src">— {e(src)}</span>'
    return f' <span class="src">— {link(src.get("label") or "source", src.get("url"))}</span>'


def note(r: dict[str, Any], tag: str = "span") -> str:
    return f' <{tag} class="note">{e(r.get("note"))}</{tag}>' if r.get("note") else ""


def item_url(r: dict[str, Any]) -> str:
    src = r.get("source") if isinstance(r.get("source"), dict) else {}
    return safe_url(r.get("url")) or safe_url(src.get("url")) or safe_url(r.get("event_url")) or ""


def item_label(r: Any) -> str:
    if not isinstance(r, dict):
        return str(r)
    if r.get("repo") and r.get("number"):
        return f"{r['repo']}#{r['number']} {r.get('title') or ''}".strip()
    if r.get("start") and r.get("title"):
        return f"{r['start']} {r['title']}"
    return str(r.get("title") or r.get("card") or r.get("task") or "")


def item_key(section: str, r: Any) -> str:
    if not isinstance(r, dict):
        return f"{section}|{r}"
    return f"{section}|{item_url(r) or item_label(r)}"


class Checks:
    """Builds the <plan-item> markup and knows which keys the JSON already marks as done."""

    def __init__(self, plan: dict[str, Any]):
        self.done_items = set(plan.get("done_items") or [])

    def attrs(self, section: str, r: Any) -> str:
        key = item_key(section, r)
        done = (r.get("done") if isinstance(r, dict) else False) or key in self.done_items
        url = item_url(r) if isinstance(r, dict) else ""
        out = f' key="{e(key)}" label="{e(item_label(r))}"'
        if url:
            out += f' url="{e(url)}"'
        return out + (" done" if done else "")

    def item(self, section: str, r: Any, content: str, sub: str = "") -> str:
        return f'<plan-item{self.attrs(section, r)}><div class="cbody">{content}</div>{sub}</plan-item>'

    def items(self, section: str, rows: list[dict[str, Any]], render, after=None) -> str:
        rows = [r for r in rows or [] if r]
        if not rows:
            return ""
        out = []
        for r in rows:
            sub = after(r) if after else ""
            out.append(self.item(section, r, render(r), f'<div class="sub">{sub}</div>' if sub else ""))
        return '<div class="items">' + "".join(out) + "</div>"

    def bullets(self, section: str, values: list[Any]) -> str:
        values = [v for v in values or [] if v]
        if not values:
            return ""
        return '<div class="items">' + "".join(self.item(section, v, e(v)) for v in values) + "</div>"


def section(name: str, title: str, body: str, cls: str = "") -> str:
    attrs = f' name="{e(name)}"' + (f' class="{e(cls)}"' if cls else "")
    return f"<plan-section{attrs}><h2>{e(title)}</h2>{body}</plan-section>" if body else ""


def titled(r: dict[str, Any]) -> str:
    title = link(r.get("title"), r.get("url")) if r.get("url") else e(r.get("title"))
    text = f" {e(r.get('text'))}" if r.get("text") else ""
    return f'<span class="t">{title}</span>{text}{source(r.get("source"))}'


def render(plan: dict[str, Any], file_label: str = "") -> str:
    mode = plan.get("mode") or "work"
    stage = plan.get("stage") or "morning"
    checks = Checks(plan)
    items, bullets = checks.items, checks.bullets
    out: list[str] = []

    eyebrow = " · ".join(
        x for x in (plan.get("date"), f"{mode} plan", "after daily" if stage == "post-daily" else None,
                    plan.get("day_class")) if x
    )
    acts = "".join(
        f'<div class="act"><b>{e(a.get("range"))}</b>{e(a.get("note"))}</div>'
        for a in (plan.get("timeline") or [])[:3]
    )
    out.append(
        f'<header class="rail"><div class="eyebrow">{e(eyebrow)}</div>'
        f"<h1>{e(plan.get('headline') or 'Plan for the day')}</h1>"
        f'{f"<div class=acts>{acts}</div>" if acts else ""}</header><main>'
    )

    dw = plan.get("deep_work") or {}
    if dw:
        status = dw.get("status") or "none"
        when = f"{dw.get('start')}–{dw.get('end')}" if dw.get("start") else ""
        label = {"scheduled": "scheduled in the calendar", "proposed": "proposed, created after the daily",
                 "none": "no window today"}.get(status, status)
        cls = "ok" if status == "scheduled" else "deep"
        content = (
            f'<span class="k {cls}">{e(label)}</span>'
            f'<span class="t">{e(dw.get("task"))}</span> {e(when)}'
            f"{note(dw, 'div')}"
            f"{(' ' + link('event', dw.get('event_url'))) if safe_url(dw.get('event_url')) else ''}"
        )
        out.append(section("deep_work", "Deep Work", f'<div class="items">{checks.item("deep_work", dw, content)}</div>',
                           "deep"))

    def priority(r: dict[str, Any]) -> str:
        kind = r.get("kind") or ""
        badge = f'<span class="k {"deep" if kind == "deep" else ""}">{e(KIND_LABEL.get(kind, kind))}</span>' if kind else ""
        est = f' <span class="note">{e(r.get("estimate"))}</span>' if r.get("estimate") else ""
        why = f'<div class="note">{e(r.get("why"))}</div>' if r.get("why") else ""
        return f"{badge}{titled(r)}{est}{why}"

    out.append(section("priorities", "Today's tasks", items("priorities", plan.get("priorities"), priority)))
    out.append(section("outside_limit", "Outside the limit", items(
        "outside_limit", plan.get("outside_limit"),
        lambda r: f'<span class="k">{e(r.get("kind"))}</span>{titled(r)}{note(r)}',
    )))

    def review(r: dict[str, Any]) -> str:
        head = link(f"{r.get('repo', '')}#{r.get('number', '')} {r.get('title', '')}".strip(), r.get("url"))
        meta = " · ".join(x for x in (r.get("author"), r.get("waiting")) if x)
        return f'<span class="t">{head}</span> <span class="note">{e(meta)}</span><div>{e(r.get("reason"))}</div>'

    out.append(section("code_review", "Code review order", items("code_review", plan.get("code_review"), review)))
    out.append(section("my_prs", "My pull requests", items(
        "my_prs", plan.get("my_prs"),
        lambda r: f'<span class="k">{e(r.get("state"))}</span>'
        f'<span class="t">{link(r.get("title"), r.get("url"))}</span>{note(r)}',
    )))
    out.append(section("needs_attention", "Needs attention", items("needs_attention", plan.get("needs_attention"), titled)))

    def meeting(r: dict[str, Any]) -> str:
        return f'<span class="t">{e(r.get("start"))}–{e(r.get("end"))} {e(r.get("title"))}</span>{note(r)}'

    out.append(section("meetings", "Meetings", items(
        "meetings", plan.get("meetings"), meeting,
        after=lambda r: bullets(f"agenda|{item_label(r)}", r.get("agenda")),
    )))

    daily = plan.get("daily_update") or {}
    daily_body = "".join(
        f"<h3>{e(label)}</h3>{bullets(f'daily_update.{key}', daily.get(key))}"
        for label, key in (("Yesterday", "yesterday"), ("Today", "today"), ("Blockers", "blockers"))
        if daily.get(key)
    )
    out.append(section("daily_update", "For the daily", daily_body))

    post = plan.get("post_daily") or {}
    post_body = "".join(
        f"<h3>{e(label)}</h3>{bullets(f'post_daily.{key}', post.get(key))}"
        for label, key in POST_DAILY
        if post.get(key)
    )
    out.append(section("post_daily", "After the daily", post_body))
    out.append(section("tomorrow_prep", "Prep for tomorrow", items("tomorrow_prep", plan.get("tomorrow_prep"), titled)))
    out.append(section("follow_ups", "Follow-ups", items("follow_ups", plan.get("follow_ups"), titled)))
    out.append(section("resolved", "Resolved", items("resolved", plan.get("resolved"), titled)))
    out.append(section("notion_changes", "Notion changes", items(
        "notion_changes", plan.get("notion_changes"),
        lambda r: f'<span class="k {"ok" if r.get("status") == "applied" else ""}">{e(r.get("status"))}</span>'
        f'<span class="t">{link(r.get("card"), r.get("url"))}</span> {e(r.get("change"))}',
    )))
    missing = plan.get("missing_sources") or []
    if missing:
        out.append(
            '<p class="note">Missing sources: '
            + "; ".join(f"{e(m.get('source'))} ({e(m.get('reason'))})" for m in missing)
            + "</p>"
        )
    out.append(f'<p class="note">Generated {e(plan.get("generated_at"))}</p></main>')
    out.insert(0, f'<plan-page file="{e(file_label)}">')
    out.append("</plan-page>")

    title = f"{plan.get('date', '')} {mode} plan"
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        f"<meta name=\"daily-workflow-plan\" content=\"{PAGE_FORMAT}\">"
        f"<title>{e(title)}</title>"
        "<link rel=\"stylesheet\" href=\"assets/plan.css\">"
        "<script defer src=\"assets/plan.js\"></script></head>"
        "<body>"
        + "".join(out)
        + "</body></html>\n"
    )


POST_DAILY = (
    ("Plan changes", "plan_changes"), ("Team blockers", "team_blockers"),
    ("Who needs help", "needs_help"), ("Agreed", "agreed"), ("Decisions", "decisions"),
)
LIST_SECTIONS = ("priorities", "outside_limit", "code_review", "my_prs", "needs_attention", "meetings",
                 "tomorrow_prep", "follow_ups", "resolved", "notion_changes")


def all_items(plan: dict[str, Any]):
    """Every checkable item as (key, item); the same keys the page uses."""
    dw = plan.get("deep_work")
    if isinstance(dw, dict) and dw:
        yield item_key("deep_work", dw), dw
    for name in LIST_SECTIONS:
        for r in plan.get(name) or []:
            if not r:
                continue
            yield item_key(name, r), r
            if name == "meetings" and isinstance(r, dict):
                for a in r.get("agenda") or []:
                    if a:
                        yield item_key(f"agenda|{item_label(r)}", a), a
    for group, keys in (("daily_update", ("yesterday", "today", "blockers")),
                        ("post_daily", tuple(k for _, k in POST_DAILY))):
        for key in keys:
            for v in (plan.get(group) or {}).get(key) or []:
                if v:
                    yield item_key(f"{group}.{key}", v), v


def mark_done(plan: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Marks the ticked items done in the plan. Returns the matched items (with their URL, so the caller can update
    Notion cards) and the unknown keys."""
    wanted = list(dict.fromkeys(keys))
    found: dict[str, dict[str, Any]] = {}
    done_items = list(plan.get("done_items") or [])
    for key, r in all_items(plan):
        if key not in wanted or key in found:
            continue
        if isinstance(r, dict):
            r["done"] = True
        elif key not in done_items:
            done_items.append(key)
        found[key] = {"key": key, "label": item_label(r), "url": item_url(r) if isinstance(r, dict) else ""}
    if done_items:
        plan["done_items"] = done_items
    return {"done": [found[k] for k in wanted if k in found], "unknown": [k for k in wanted if k not in found]}


def copy_assets(names: tuple[str, ...], target: Path) -> None:
    """Pages link their assets relatively; overwrite them on every render so every page gets the current version."""
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        tmp = target / f".{name}.tmp"
        shutil.copyfile(ASSETS_DIR / name, tmp)
        tmp.replace(target / name)


def _write_page(json_path: Path, file_label: str) -> Path:
    plan = json.loads(json_path.read_text(encoding="utf-8"))
    html_path = json_path.with_suffix(".html")
    tmp = html_path.with_name(f".{html_path.name}.tmp")
    tmp.write_text(render(plan, file_label), encoding="utf-8")
    tmp.replace(html_path)
    return html_path


def render_file(json_path: Path, file_label: str = "") -> Path:
    """Renders the plan, then every other plan in the folder: the assets are shared, so old pages need the
    current markup too."""
    copy_assets(ASSETS, json_path.parent / "assets")
    html_path = _write_page(json_path, file_label or f"plans/{json_path.name}")
    for other in sorted(json_path.parent.glob("*.json")):
        if other.resolve() == json_path.resolve():
            continue
        try:
            _write_page(other, f"plans/{other.name}")
        except (OSError, ValueError, TypeError, AttributeError) as err:
            core.log(f"[plan] cannot re-render {other.name}: {err!r}")
    return html_path
