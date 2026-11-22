import datetime as dt
import json
import os
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

from wl import collector, core, plan, summarizer, views  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
