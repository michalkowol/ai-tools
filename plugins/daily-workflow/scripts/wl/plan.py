"""Renders plans/YYYY-MM-DD[-home].json into a fixed HTML page.

Every value is escaped and only http(s) links are kept: the plan holds text
gathered from email, Slack and transcripts, which is data, never markup."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

CSS = """
:root{--bg:#FAF9F5;--wash:#F0EEE6;--ink:#141413;--body:#3D3D3A;--muted:#87867F;--line:#D1CFC5;
--clay:#D97757;--olive:#788C5D;--serif:Georgia,"Times New Roman",serif;
--sans:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;--mono:ui-monospace,Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--body);font:15px/1.55 var(--sans)}
main{max-width:860px;margin:0 auto;padding:40px 24px 80px}
.top{background:var(--wash);border-bottom:1px solid var(--line)}
.eyebrow{font:12px var(--mono);text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
h1{font:600 34px/1.2 var(--serif);color:var(--ink);margin:6px 0 20px}
h2{font:600 18px var(--sans);color:var(--ink);margin:36px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.acts{display:grid;grid-template-columns:repeat(3,1fr);gap:0}
.act{padding:0 16px;border-left:1px solid var(--line)}.act:first-child{border-left:0;padding-left:0}
.act b{display:block;color:var(--ink)}
ol,ul{padding-left:22px;margin:6px 0}li{margin:8px 0}
li::marker{color:var(--muted)}
.t{font-weight:600;color:var(--ink)}
.k{display:inline-block;font:11px var(--mono);padding:1px 7px;border-radius:9px;background:#E3DACC;color:var(--ink);margin-right:6px}
.k.deep{background:var(--clay);color:#fff}.k.ok{background:var(--olive);color:#fff}
.src a,.src{color:var(--muted)}a{color:var(--body)}
.note{color:var(--muted);font-size:13px}
.deep-box{border-left:3px solid var(--clay);padding:8px 14px;background:#fff}
code{font:13px var(--mono);background:var(--wash);padding:1px 5px;border-radius:4px}
@media(max-width:640px){.acts{grid-template-columns:1fr}.act{border-left:0;border-top:1px solid var(--line);padding:8px 0}h1{font-size:27px}}
"""

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


def items(rows: list[dict[str, Any]], render) -> str:
    rows = [r for r in rows or [] if r]
    if not rows:
        return ""
    return "<ol>" + "".join(f"<li>{render(r)}</li>" for r in rows) + "</ol>"


def bullets(values: list[Any]) -> str:
    values = [v for v in values or [] if v]
    return "<ul>" + "".join(f"<li>{e(v)}</li>" for v in values) + "</ul>" if values else ""


def section(title: str, body: str) -> str:
    return f"<section><h2>{e(title)}</h2>{body}</section>" if body else ""


def titled(r: dict[str, Any]) -> str:
    title = link(r.get("title"), r.get("url")) if r.get("url") else e(r.get("title"))
    text = f" {e(r.get('text'))}" if r.get("text") else ""
    return f'<span class="t">{title}</span>{text}{source(r.get("source"))}'


def render(plan: dict[str, Any]) -> str:
    mode = plan.get("mode") or "work"
    stage = plan.get("stage") or "morning"
    out: list[str] = []

    eyebrow = " · ".join(
        x for x in (plan.get("date"), f"{mode} briefing", "after daily" if stage == "post-daily" else None,
                    plan.get("day_class")) if x
    )
    acts = "".join(
        f'<div class="act"><b>{e(a.get("range"))}</b>{e(a.get("note"))}</div>'
        for a in (plan.get("timeline") or [])[:3]
    )
    out.append(
        f'<div class="top"><main><div class="eyebrow">{e(eyebrow)}</div>'
        f"<h1>{e(plan.get('headline') or 'Plan for the day')}</h1>"
        f'{f"<div class=acts>{acts}</div>" if acts else ""}</main></div><main>'
    )

    dw = plan.get("deep_work") or {}
    if dw:
        status = dw.get("status") or "none"
        when = f"{dw.get('start')}–{dw.get('end')}" if dw.get("start") else ""
        label = {"scheduled": "scheduled in the calendar", "proposed": "proposed, created after the daily",
                 "none": "no window today"}.get(status, status)
        cls = "ok" if status == "scheduled" else "deep"
        out.append(section("Deep Work", (
            f'<div class="deep-box"><span class="k {cls}">{e(label)}</span>'
            f'<span class="t">{e(dw.get("task"))}</span> {e(when)}'
            f"{note(dw, 'div')}"
            f"{(' ' + link('event', dw.get('event_url'))) if safe_url(dw.get('event_url')) else ''}</div>"
        )))

    def priority(r: dict[str, Any]) -> str:
        kind = r.get("kind") or ""
        badge = f'<span class="k {"deep" if kind == "deep" else ""}">{e(KIND_LABEL.get(kind, kind))}</span>' if kind else ""
        est = f' <span class="note">{e(r.get("estimate"))}</span>' if r.get("estimate") else ""
        why = f'<div class="note">{e(r.get("why"))}</div>' if r.get("why") else ""
        return f"{badge}{titled(r)}{est}{why}"

    out.append(section("Today's tasks", items(plan.get("priorities"), priority)))
    out.append(section("Outside the limit", items(
        plan.get("outside_limit"),
        lambda r: f'<span class="k">{e(r.get("kind"))}</span>{titled(r)}{note(r)}',
    )))

    def review(r: dict[str, Any]) -> str:
        head = link(f"{r.get('repo', '')}#{r.get('number', '')} {r.get('title', '')}".strip(), r.get("url"))
        meta = " · ".join(x for x in (r.get("author"), r.get("waiting")) if x)
        return f'<span class="t">{head}</span> <span class="note">{e(meta)}</span><div>{e(r.get("reason"))}</div>'

    out.append(section("Code review order", items(plan.get("code_review"), review)))
    out.append(section("My pull requests", items(
        plan.get("my_prs"),
        lambda r: f'<span class="k">{e(r.get("state"))}</span>'
        f'<span class="t">{link(r.get("title"), r.get("url"))}</span>{note(r)}',
    )))
    out.append(section("Needs attention", items(plan.get("needs_attention"), titled)))

    def meeting(r: dict[str, Any]) -> str:
        agenda = bullets(r.get("agenda"))
        return f'<span class="t">{e(r.get("start"))}–{e(r.get("end"))} {e(r.get("title"))}</span>{note(r)}{agenda}'

    out.append(section("Meetings", items(plan.get("meetings"), meeting)))

    daily = plan.get("daily_update") or {}
    daily_body = "".join(
        f"<p class=t>{e(label)}</p>{bullets(daily.get(key))}"
        for label, key in (("Yesterday", "yesterday"), ("Today", "today"), ("Blockers", "blockers"))
        if daily.get(key)
    )
    out.append(section("For the daily", daily_body))

    post = plan.get("post_daily") or {}
    post_body = "".join(
        f"<p class=t>{e(label)}</p>{bullets(post.get(key))}"
        for label, key in (
            ("Plan changes", "plan_changes"), ("Team blockers", "team_blockers"),
            ("Who needs help", "needs_help"), ("Agreed", "agreed"), ("Decisions", "decisions"),
        )
        if post.get(key)
    )
    out.append(section("After the daily", post_body))
    out.append(section("Prep for tomorrow", items(plan.get("tomorrow_prep"), titled)))
    out.append(section("Follow-ups", items(plan.get("follow_ups"), titled)))
    out.append(section("Resolved", items(plan.get("resolved"), titled)))
    out.append(section("Notion changes", items(
        plan.get("notion_changes"),
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

    title = f"{plan.get('date', '')} {mode} plan"
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        f"<title>{e(title)}</title><style>{CSS}</style></head><body>"
        + "".join(out)
        + "</body></html>\n"
    )


def render_file(json_path: Path) -> Path:
    plan = json.loads(json_path.read_text(encoding="utf-8"))
    html_path = json_path.with_suffix(".html")
    tmp = html_path.with_name(f".{html_path.name}.tmp")
    tmp.write_text(render(plan), encoding="utf-8")
    tmp.replace(html_path)
    return html_path
