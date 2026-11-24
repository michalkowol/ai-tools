import datetime as dt
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import tomllib
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from wl import collector, core, github, inbox, plan, summarizer, views  # noqa: E402

FAKE_CLAUDE = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    data = json.load(sys.stdin)
    log = os.environ.get("FAKE_CLAUDE_LOG")
    if log:
        with open(log, "a") as fh:
            fh.write(json.dumps({"argv": sys.argv[1:], "data": data}) + "\\n")
    if os.environ.get("FAKE_CLAUDE_FAIL"):
        sys.exit(3)
    prompts = [p for c in data["checkpoints"] for p in c.get("prompts", [])]
    entry = {
        "summary": "Worked on " + (prompts[0] if prompts else "stuff"),
        "status": "in_progress",
        "accomplished": ["Implemented validation"],
        "decisions": ["Chose batch processing"],
        "problems_solved": [],
        "blockers": [],
        "next_steps": ["Finish tests"],
        "tags": ["backend"],
        "jira": "",
    }
    print(json.dumps({"type": "result", "is_error": False, "result": json.dumps(entry), "structured_output": entry}))
    """
)


def sh(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


class WorklogTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "worklog"
        fake = self.root / "claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.claude_log = self.root / "claude.log"
        self.env = mock.patch.dict(
            os.environ,
            {
                "WORKLOG_HOME": str(self.home),
                "WORKLOG_CLAUDE_BIN": str(fake),
                "FAKE_CLAUDE_LOG": str(self.claude_log),
                "TZ": "CET-1CEST,M3.5.0,M10.5.0/3",
            },
        )
        self.env.start()
        time.tzset()
        os.environ.pop("WORKLOG_DISABLE", None)
        core.reset_config_cache()

    def tearDown(self):
        self.env.stop()
        time.tzset()
        core.reset_config_cache()
        self.tmp.cleanup()

    def make_repo(self):
        """A repo with origin 'proj' and a linked worktree 'proj-1234', like ai mounts it."""
        main = self.root / "src" / "proj"
        main.mkdir(parents=True)
        sh("git", "init", "-q", "-b", "main", cwd=main)
        sh("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init", cwd=main)
        sh("git", "remote", "add", "origin", "git@github.com:org/proj.git", cwd=main)
        wt = self.root / "workspace"
        sh("git", "worktree", "add", "-q", "-b", "feature/proj-1234", str(wt), cwd=main)
        (wt / "a.txt").write_text("x\n")
        return main, wt

    def transcript(self, rows):
        path = self.root / "transcript.jsonl"
        with open(path, "a") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        return path

    def hook(self, event, **payload):
        payload.setdefault("session_id", "s1")
        return collector.handle_hook(event, json.dumps(payload))


class ConfigTest(WorklogTestCase):
    def test_example_config_parses(self):
        parsed = tomllib.loads((core.PLUGIN_ROOT / "config.example.toml").read_text())
        self.assertTrue(parsed["notion"]["view_top"].startswith("view://"))

    def test_jira_key_respects_project_keys(self):
        core.ensure_home()
        (self.home / "config.toml").write_text('[worklog]\njira_project_keys = ["PROJ"]\n')
        core.reset_config_cache()
        self.assertEqual(core.find_jira_key("feature/proj-1234"), "PROJ-1234")
        self.assertIsNone(core.find_jira_key("fix/utf-8-encoding"))

    def test_last_workday_skips_weekend(self):
        self.assertEqual(core.last_workday(dt.date(2026, 11, 23)), dt.date(2026, 11, 20))
        self.assertEqual(core.last_workday(dt.date(2026, 11, 24)), dt.date(2026, 11, 23))

    def test_posix_tz_is_used(self):
        self.assertEqual(core.now().utcoffset(), dt.timedelta(hours=1))


class CollectorTest(WorklogTestCase):
    def test_git_meta_in_worktree(self):
        _, wt = self.make_repo()
        meta = collector.git_meta(str(wt))
        self.assertEqual(meta["repo"], "proj")
        self.assertEqual(meta["worktree"], "workspace")
        self.assertEqual(meta["branch"], "feature/proj-1234")
        self.assertEqual(meta["git"]["dirty_files"], 1)

    def test_git_meta_outside_git(self):
        meta = collector.git_meta(str(self.root))
        self.assertIsNone(meta["repo"])

    def test_stop_records_prompts_reply_and_cursor(self):
        _, wt = self.make_repo()
        tr = self.transcript([
            {"type": "user", "message": {"role": "user", "content": "add event validation"}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "x"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Added it."}]}},
        ])
        self.hook("Stop", cwd=str(wt), transcript_path=str(tr), last_assistant_message="Done, validation added.")
        state = collector.load_state("s1")
        cps = summarizer.load_checkpoints("s1", 0)
        self.assertEqual(len(cps), 1)
        cp = cps[0]
        self.assertEqual(cp["prompts"], ["add event validation"])
        self.assertEqual(cp["reply"], "Done, validation added.")
        self.assertEqual(cp["jira"], "PROJ-1234")
        self.assertEqual(cp["transcript"]["to"], tr.stat().st_size)
        self.assertEqual(state["transcript_offset"], tr.stat().st_size)

        self.transcript([{"type": "user", "message": {"role": "user", "content": "now the tests"}}])
        self.hook("Stop", cwd=str(wt), transcript_path=str(tr))
        second = summarizer.load_checkpoints("s1", 1)[0]
        self.assertEqual(second["prompts"], ["now the tests"])
        self.assertEqual(second["seq"], 2)

    def test_post_tool_use_signals(self):
        self.hook("PostToolUse", cwd=str(self.root), tool_name="Bash", tool_input={"command": "ls -la"})
        self.assertEqual(summarizer.load_checkpoints("s1", 0), [])
        self.hook("PostToolUse", cwd=str(self.root), tool_name="Bash",
                  tool_input={"command": "./gradlew test && git commit -m x && gh pr create --fill"})
        self.hook("PostToolUse", cwd=str(self.root),
                  tool_name="mcp__claude_ai_Atlassian_MCP__transitionJiraIssue",
                  tool_input={"issueIdOrKey": "PROJ-1"})
        cps = summarizer.load_checkpoints("s1", 0)
        self.assertEqual(cps[0]["signals"], ["git_commit", "pr_created", "tests_run"])
        self.assertEqual(cps[1]["signals"], ["jira_transition"])
        self.assertIn("PROJ-1", cps[1]["detail"])

    def test_disabled_inside_summarizer(self):
        with mock.patch.dict(os.environ, {"WORKLOG_DISABLE": "1"}):
            self.hook("SessionStart", cwd=str(self.root), source="startup")
        self.assertFalse(core.state_dir().exists() and any(core.state_dir().iterdir()))

    def test_broken_input_never_fails(self):
        self.assertEqual(collector.handle_hook("Stop", "not json"), 0)
        self.assertEqual(collector.handle_hook("Stop", "{}"), 0)

    def test_session_end_does_not_spawn_summary(self):
        with mock.patch.object(collector, "spawn_summarizer") as spawn:
            self.hook("SessionEnd", cwd=str(self.root), reason="prompt_input_exit")
            spawn.assert_not_called()
            self.hook("PreCompact", cwd=str(self.root), trigger="auto")
            spawn.assert_called_once_with("s1")
        self.assertTrue(collector.load_state("s1").get("ended_at"))

    def test_stop_spawns_summary_after_threshold(self):
        with mock.patch.object(collector, "spawn_summarizer") as spawn:
            self.hook("SessionStart", cwd=str(self.root), source="startup")
            self.hook("Stop", cwd=str(self.root))
            spawn.assert_not_called()
            state = collector.load_state("s1")
            state["started_at"] = (core.now() - dt.timedelta(minutes=16)).isoformat()
            collector.save_state(state)
            self.hook("Stop", cwd=str(self.root))
            spawn.assert_called_once_with("s1")


class SummarizerTest(WorklogTestCase):
    def record_turn(self, wt, prompt):
        tr = self.transcript([{"type": "user", "message": {"role": "user", "content": prompt}}])
        self.hook("Stop", cwd=str(wt), transcript_path=str(tr), last_assistant_message="ok")

    def test_summary_entry_cursor_day_and_git(self):
        _, wt = self.make_repo()
        with mock.patch.object(collector, "spawn_summarizer"):
            self.record_turn(wt, "add event validation")
            self.record_turn(wt, "write tests")
        created = summarizer.summarize_session("s1")
        self.assertEqual(len(created), 1)
        entry = created[0]
        self.assertEqual(entry["id"], "s1:1-2")
        self.assertEqual(entry["repo"], "proj")
        self.assertEqual(entry["jira"], "PROJ-1234")
        self.assertIn("proj", entry["tags"])
        month_file = core.entries_dir() / entry["date"][:7] / "s1.jsonl"
        self.assertTrue(month_file.exists())
        self.assertEqual(collector.load_cursor("s1")["last_summarized_seq"], 2)
        day_md = (core.days_dir() / f"{entry['date']}.md").read_text()
        self.assertIn("Worked on add event validation", day_md)
        self.assertIn("PROJ-1234", day_md)
        log = core.git(self.home, "log", "--oneline")
        self.assertIn("worklog:", log)

        call = json.loads(self.claude_log.read_text().splitlines()[0])
        argv = call["argv"]
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertIn("disableAllHooks", argv[argv.index("--settings") + 1])

        self.assertEqual(summarizer.summarize_session("s1"), [])

    def test_failure_keeps_cursor(self):
        _, wt = self.make_repo()
        with mock.patch.object(collector, "spawn_summarizer"):
            self.record_turn(wt, "something")
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_FAIL": "1"}):
            self.assertEqual(summarizer.summarize_session("s1"), [])
        self.assertEqual(collector.load_cursor("s1")["last_summarized_seq"], 0)
        self.assertEqual(len(summarizer.summarize_session("s1")), 1)

    def test_empty_checkpoints_skip_llm(self):
        self.hook("SessionStart", cwd=str(self.root), source="startup")
        self.hook("SessionEnd", cwd=str(self.root), reason="other")
        self.assertEqual(summarizer.summarize_session("s1"), [])
        self.assertFalse(self.claude_log.exists())
        self.assertEqual(collector.load_cursor("s1")["last_summarized_seq"], 2)

    def test_catch_up_all_sessions(self):
        _, wt = self.make_repo()
        with mock.patch.object(collector, "spawn_summarizer"):
            for sid in ("a", "b"):
                tr = self.transcript([{"type": "user", "message": {"role": "user", "content": f"task {sid}"}}])
                collector.handle_hook("Stop", json.dumps({"session_id": sid, "cwd": str(wt), "transcript_path": str(tr)}))
        self.assertEqual(sorted(summarizer.pending_sessions()), ["a", "b"])
        created = summarizer.summarize_all()
        self.assertEqual(sorted(e["session_id"] for e in created), ["a", "b"])
        self.assertEqual(summarizer.pending_sessions(), [])
        ctx = views.context(core.now().date())
        self.assertEqual(len(ctx["entries"]), 2)
        self.assertEqual(len(ctx["open_threads"]), 2)


class CliTest(WorklogTestCase):
    def run_cli(self, *args, stdin=""):
        env = dict(os.environ)
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "worklog.py"), *args],
            input=stdin, capture_output=True, text=True, env=env, check=False,
        )

    def test_hook_flush_and_queries_via_cli(self):
        _, wt = self.make_repo()
        tr = self.transcript([{"type": "user", "message": {"role": "user", "content": "refactor retries"}}])
        self.assertEqual(self.run_cli("hook", "SessionStart",
                                      stdin=json.dumps({"session_id": "s9", "cwd": str(wt), "transcript_path": str(tr)})).returncode, 0)
        out = self.run_cli("flush", "--session", "${CLAUDE_SESSION_ID}")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Worked on refactor retries", out.stdout)
        entries = json.loads(self.run_cli("entries", "--since", core.now().date().isoformat()).stdout)
        self.assertEqual(entries[0]["session_id"], "s9")
        dates = json.loads(self.run_cli("dates").stdout)
        self.assertIn("last_workday", dates)
        status = json.loads(self.run_cli("status").stdout)
        self.assertEqual(status["sessions"][0]["pending_checkpoints"], 0)

    def test_meetings_lists_transcripts_for_the_day(self):
        core.ensure_home()
        day = core.now().date().isoformat()
        (core.meetings_dir() / f"{day}-daily.txt").write_text("Alice: blocked on API")
        (core.meetings_dir() / "2020-01-01-daily.txt").write_text("old")
        found = json.loads(self.run_cli("meetings").stdout)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["path"].endswith(f"{day}-daily.txt"))


class PlanTest(WorklogTestCase):
    def test_render_escapes_and_filters_links(self):
        core.ensure_home()
        data = {
            "date": "2026-11-23", "mode": "work", "stage": "morning",
            "headline": "<script>alert(1)</script>",
            "timeline": [{"range": "9 – 11", "note": "Daily"}],
            "priorities": [{"title": "Task", "kind": "deep", "url": "javascript:alert(1)"}],
            "needs_attention": [{"title": "Reply", "text": "<b>x</b>", "source": {"label": "in #proj", "url": "https://slack.com/x"}}],
            "deep_work": {"status": "proposed", "task": "PROJ-1", "start": "11:00", "end": "13:00", "note": "after daily"},
            "missing_sources": [{"source": "Gmail", "reason": "not signed in"}],
        }
        path = core.plans_dir() / "2026-11-23.json"
        path.write_text(json.dumps(data))
        html_path = plan.render_file(path)
        page = html_path.read_text()
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("javascript:", page)
        self.assertIn('href="https://slack.com/x"', page)
        self.assertIn("proposed, created after the daily", page)
        self.assertIn("Missing sources", page)
        self.assertNotIn("Resolved", page)


class GithubEstimateTest(unittest.TestCase):
    def test_estimate_by_changed_files(self):
        cases = {1: "0.25 x 🍅", 3: "0.25 x 🍅", 4: "0.5 x 🍅", 9: "0.5 x 🍅", 10: "1 x 🍅", 19: "1 x 🍅",
                 20: "2 x 🍅", 39: "2 x 🍅", 40: "3 x 🍅", 400: "3 x 🍅"}
        for files, expected in cases.items():
            self.assertEqual(github.estimate(files), expected, files)
        self.assertIsNone(github.estimate(None))

    def test_small_is_under_ten_files(self):
        self.assertTrue(github.is_small(9))
        self.assertFalse(github.is_small(10))
        self.assertFalse(github.is_small(None))

    def test_slim_carries_size_estimate(self):
        pr = {"url": "https://github.com/org/shop/pull/412", "number": 412, "title": "T", "changedFiles": 7,
              "additions": 120, "deletions": 30, "author": {"login": "alice"}}
        self.assertEqual(github.slim(pr, "me")["size"],
                         {"additions": 120, "deletions": 30, "files": 7, "estimate": "0.5 x 🍅", "small": True})


class InboxTest(WorklogTestCase):
    run_cli = CliTest.run_cli

    def test_first_window_starts_at_last_workday(self):
        win = json.loads(self.run_cli("inbox", "start").stdout)
        self.assertTrue(win["first_run"])
        expected = core.last_workday(core.now().date()).isoformat()
        self.assertEqual(win["since_date"], expected)
        self.assertTrue(win["since"].startswith(expected + "T00:00:00"))

    def test_record_moves_cursor_and_filters_duplicates(self):
        urls = ["https://team.slack.com/archives/C1/p1?thread_ts=1.2", "https://github.com/org/shop/pull/412/"]
        out = self.run_cli("inbox", "record", "--cursor", "2026-11-23T09:30:00+01:00", stdin=json.dumps(urls))
        self.assertEqual(out.returncode, 0, out.stderr)
        win = json.loads(self.run_cli("inbox", "start").stdout)
        self.assertFalse(win["first_run"])
        self.assertEqual(win["since"], "2026-11-23T09:30:00+01:00")
        checked = json.loads(self.run_cli("inbox", "check", stdin=json.dumps([
            "https://github.com/org/shop/pull/412",
            "https://team.slack.com/archives/C1/p1?thread_ts=9.9",
            "https://mail.google.com/mail/u/0/#all/abc",
        ])).stdout)
        self.assertEqual(checked["known"], ["https://github.com/org/shop/pull/412"])
        self.assertEqual(len(checked["new"]), 2)

    def test_record_without_cursor_keeps_window(self):
        self.run_cli("inbox", "record", "--cursor", "2026-11-23T09:30:00+01:00", stdin="[]")
        self.run_cli("inbox", "record", "https://mail.google.com/mail/u/0/#all/abc")
        state = json.loads(inbox.state_path().read_text())
        self.assertEqual(state["cursor"], "2026-11-23T09:30:00+01:00")
        self.assertEqual(len(state["seen"]), 1)
        checked = json.loads(self.run_cli("inbox", "check", "https://mail.google.com/mail/u/0/#all/abc",
                                          "https://mail.google.com/mail/u/0/#all/xyz").stdout)
        self.assertEqual(checked["known"], ["https://mail.google.com/mail/u/0/#all/abc"])

    def test_registry_prunes_after_30_days(self):
        old = (core.now() - dt.timedelta(days=31)).isoformat(timespec="seconds")
        core.write_json_atomic(inbox.state_path(), {"cursor": "", "seen": {"https://x.test/old": old}})
        self.assertEqual(inbox.check(["https://x.test/old"])["new"], ["https://x.test/old"])
        inbox.record(["https://x.test/new"], None)
        self.assertEqual(list(json.loads(inbox.state_path().read_text())["seen"]), ["https://x.test/new"])

    def test_order_blocking_then_due_then_oldest(self):
        entries = [
            {"id": "old", "created_at": "2026-11-20T10:00:00+01:00", "cards": [{}]},
            {"id": "newer", "created_at": "2026-11-22T10:00:00+01:00", "cards": [{}]},
            {"id": "due", "created_at": "2026-11-22T11:00:00+01:00", "cards": [{"due": "2026-11-25"}]},
            {"id": "blocking", "created_at": "2026-11-22T12:00:00+01:00", "waiting_on_me": True, "cards": [{}]},
            {"title": "no id"},
        ]
        self.assertEqual([x["id"] for x in inbox.order(entries)], ["blocking", "due", "old", "newer"])

    def page_data(self, **extra):
        data = {
            "date": "2026-11-23", "generated_at": "2026-11-23T09:31:04+01:00",
            "captured": {"created": 1, "skipped": 2},
            "agenda_cards": [{"id": "a1", "name": "Alice"}],
            "entries": [{
                "id": "p1", "url": "javascript:alert(1)", "title": "<img src=x onerror=alert(1)>",
                "source": {"label": "PR org/shop#412 by alice", "url": "https://github.com/org/shop/pull/412"},
                "age": "4 d", "created_at": "2026-11-19T10:00:00+01:00", "waiting_on_me": True,
                "why": "</inbox-why><script>alert(2)</script>",
                "cards": [{"outcome": "next", "title": "Review Alice's batch processing (shop#412)", "category": ["Work"],
                           "estimate": "1 x 🍅", "priority": "P1", "reminder": "2026-11-23", "due": "", "project": "Hiring"}],
            }, {
                "id": "p2", "url": "https://www.notion.so/p2", "title": "Zmiany na stronie", "source": None, "age": "2 d",
                "why": "Two independent changes.",
                "cards": [
                    {"outcome": "next", "title": "Dodać zdjęcie sali", "category": ["Home"], "estimate": "0.5 x 🍅"},
                    {"outcome": "bogus", "title": "Dodać przerywniki", "category": ["Work", "Home"]},
                ],
            }],
            "missing_sources": [{"source": "Gmail", "reason": "not signed in"}],
        }
        data.update(extra)
        return data

    def render_page(self, data, name="2026-11-23-0931.json"):
        core.ensure_home()
        path = inbox.inbox_dir() / name
        path.write_text(json.dumps(data))
        out = self.run_cli("render-inbox", f"inbox/{name}")
        return out, path.with_suffix(".html")

    def test_render_single_and_split_entries_as_markup(self):
        out, html_path = self.render_page(self.page_data())
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("2026-11-23-0931.html", out.stdout)
        page = html_path.read_text()
        self.assertIn('<meta name="daily-workflow-inbox" content="1">', page)
        self.assertIn('<inbox-app file="inbox/2026-11-23-0931.json" date="2026-11-23"', page)
        self.assertIn('captured="1" skipped="2"', page)
        self.assertIn('<inbox-agenda name="Alice"></inbox-agenda>', page)
        self.assertIn('<inbox-missing source="Gmail">not signed in</inbox-missing>', page)
        self.assertIn('<inbox-entry entry-id="p1" age="4 d" waiting>', page)
        self.assertIn('<inbox-original href="https://github.com/org/shop/pull/412" label="PR org/shop#412 by alice">', page)
        self.assertIn('<inbox-card outcome="next" category="Work" estimate="1 x 🍅" priority="P1" reminder="2026-11-23" '
                      'project="Hiring">Review Alice&#x27;s batch processing (shop#412)</inbox-card>', page)
        self.assertIn('<inbox-entry entry-id="p2" age="2 d" page-url="https://www.notion.so/p2">', page)
        self.assertIn('<inbox-original>Zmiany na stronie</inbox-original>', page)
        self.assertIn('<inbox-card outcome="next" category="Home" estimate="0.5 x 🍅">Dodać zdjęcie sali</inbox-card>', page)
        self.assertIn('<inbox-card outcome="keep" category="Work+Home">Dodać przerywniki</inbox-card>', page)
        self.assertLess(page.index('entry-id="p1"'), page.index('entry-id="p2"'))
        for name in inbox.ASSETS:
            self.assertEqual((inbox.inbox_dir() / "assets" / name).read_bytes(), (inbox.ASSETS_DIR / name).read_bytes())
            self.assertIn(f'assets/{name}', page)
        self.assertNotIn("<style", page)

    def test_render_fills_empty_first_card_title_with_original(self):
        data = self.page_data(entries=[{
            "id": "t1", "title": "Review shop#250: Add release notes endpoint", "created_at": "2026-11-22T10:00:00+01:00",
            "cards": [{"outcome": "trash", "title": ""}, {"outcome": "next", "title": ""}],
        }])
        _, html_path = self.render_page(data)
        page = html_path.read_text()
        self.assertIn('<inbox-card outcome="trash" category="Work">Review shop#250: Add release notes endpoint</inbox-card>', page)
        self.assertIn('<inbox-card outcome="next" category="Work"></inbox-card>', page)

    def test_render_escapes_content_and_drops_unsafe_links(self):
        _, html_path = self.render_page(self.page_data())
        page = html_path.read_text()
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("</inbox-why><script>", page)
        self.assertNotIn("javascript:", page)

    def test_render_overwrites_stale_assets(self):
        stale = inbox.inbox_dir() / "assets" / "inbox.css"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("old")
        self.render_page(self.page_data())
        self.assertEqual(stale.read_bytes(), (inbox.ASSETS_DIR / "inbox.css").read_bytes())

    def test_render_rejects_old_format_and_entries_without_cards(self):
        out, _ = self.render_page({"date": "2026-11-23", "cards": [{"id": "p1", "proposal": {}}]})
        self.assertEqual(out.returncode, 1)
        self.assertIn("old page JSON format", out.stderr)
        out, _ = self.render_page({"date": "2026-11-23", "entries": [{"id": "p1", "title": "x"}]})
        self.assertEqual(out.returncode, 1)
        self.assertIn("has no cards", out.stderr)

    def test_render_empty_inbox(self):
        core.ensure_home()
        path = inbox.inbox_dir() / "2026-11-23-1000.json"
        path.write_text(json.dumps({"date": "2026-11-23", "entries": []}))
        page = inbox.render_file(path, "inbox/2026-11-23-1000.json").read_text()
        self.assertIn('<inbox-app file="inbox/2026-11-23-1000.json" date="2026-11-23">\n</inbox-app>', page)


class InboxLogicTest(unittest.TestCase):
    """Runs the node tests of the page logic (assets/inbox-logic.js); skipped without node."""

    def test_node_logic_tests(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        test_file = Path(__file__).resolve().parent / "inbox_logic.test.js"
        out = subprocess.run([node, "--test", str(test_file)], capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
