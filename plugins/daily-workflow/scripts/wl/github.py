"""Collects pull request data for the briefing with gh, as one JSON document."""
from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import core

PR_FIELDS = (
    "number,title,url,author,createdAt,updatedAt,isDraft,reviewDecision,reviewRequests,"
    "additions,deletions,changedFiles,latestReviews,statusCheckRollup,headRefName,"
    "baseRefName,labels,comments"
)


class GhError(RuntimeError):
    pass


def gh_json(*args: str, timeout: float = 60) -> Any:
    try:
        out = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GhError(f"gh {' '.join(args[:3])}: {exc}") from exc
    if out.returncode != 0:
        raise GhError(f"gh {' '.join(args[:3])}: {core.truncate(out.stderr, 300)}")
    return json.loads(out.stdout or "null")


def search_prs(query: str) -> list[str]:
    data = gh_json("api", "-X", "GET", "search/issues", "-f", f"q={query}", "-f", "per_page=50")
    return [item["html_url"] for item in (data or {}).get("items", [])]


def ci_state(rollup: list[dict[str, Any]] | None) -> str:
    if not rollup:
        return "none"
    states = {(c.get("conclusion") or c.get("state") or c.get("status") or "").upper() for c in rollup}
    if states & {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}:
        return "failing"
    if states & {"PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED", "WAITING", ""}:
        return "pending"
    return "passing"


def hours_since(ts: str | None) -> float | None:
    if not ts:
        return None
    return round((core.now() - core.parse_ts(ts.replace("Z", "+00:00"))).total_seconds() / 3600, 1)


# Review estimate by changed files: (files below, estimate). Small PRs are covered by the recurring code review card.
ESTIMATE_BY_FILES = ((4, "0.25 x 🍅"), (10, "0.5 x 🍅"), (20, "1 x 🍅"), (40, "2 x 🍅"))
LARGEST_ESTIMATE = "3 x 🍅"
SMALL_ESTIMATES = ("0.25 x 🍅", "0.5 x 🍅")


def estimate(files: int | None) -> str | None:
    if files is None:
        return None
    return next((value for limit, value in ESTIMATE_BY_FILES if files < limit), LARGEST_ESTIMATE)


def is_small(files: int | None) -> bool:
    return estimate(files) in SMALL_ESTIMATES


def slim(pr: dict[str, Any], me: str) -> dict[str, Any]:
    comments = pr.get("comments") or []
    requests = pr.get("reviewRequests") or []
    requested = [r.get("login") or r.get("slug") or r.get("name") for r in requests]
    author = (pr.get("author") or {}).get("login") or ""
    return {
        "repo": "/".join(pr["url"].split("/")[3:5]),
        "number": pr["number"],
        "title": pr["title"],
        "url": pr["url"],
        "author": author,
        "author_is_bot": author.startswith("app/") or author.endswith("[bot]") or bool((pr.get("author") or {}).get("is_bot")),
        "draft": pr.get("isDraft"),
        "created_at": pr.get("createdAt"),
        "updated_at": pr.get("updatedAt"),
        "age_hours": hours_since(pr.get("createdAt")),
        "idle_hours": hours_since(pr.get("updatedAt")),
        "size": {"additions": pr.get("additions"), "deletions": pr.get("deletions"), "files": pr.get("changedFiles"),
                 "estimate": estimate(pr.get("changedFiles")), "small": is_small(pr.get("changedFiles"))},
        "review_decision": pr.get("reviewDecision") or None,
        "review_requested": [r for r in requested if r],
        "requested_from_me_directly": me in requested,
        "latest_reviews": [
            {"author": (r.get("author") or {}).get("login"), "state": r.get("state"), "at": r.get("submittedAt")}
            for r in (pr.get("latestReviews") or [])
        ],
        "ci": ci_state(pr.get("statusCheckRollup")),
        "labels": [label.get("name") for label in (pr.get("labels") or [])],
        "comments_count": len(comments),
        "last_comments": [
            {
                "author": (c.get("author") or {}).get("login"),
                "at": c.get("createdAt"),
                "body": core.truncate(c.get("body"), 400),
            }
            for c in comments[-3:]
        ],
        "branch": pr.get("headRefName"),
    }


def gather() -> dict[str, Any]:
    cfg = core.config().get("github") or {}
    result: dict[str, Any] = {
        "generated_at": core.now_iso(),
        "me": None,
        "review_requested": [],
        "team_repo_prs": [],
        "my_prs": [],
        "errors": [],
    }
    try:
        me = gh_json("api", "user")["login"]
    except (GhError, KeyError, TypeError) as exc:
        result["errors"].append(f"GitHub user lookup failed, is gh authenticated? {exc}")
        return result
    result["me"] = me

    def details(url: str) -> dict[str, Any] | None:
        try:
            return slim(gh_json("pr", "view", url, "--json", PR_FIELDS), me)
        except GhError as exc:
            result["errors"].append(str(exc))
            return None

    def search(query: str) -> list[str]:
        try:
            return search_prs(query)
        except GhError as exc:
            result["errors"].append(str(exc))
            return []

    # review-requested includes requests to teams I am in, user-review-requested only direct ones.
    requested_urls = search("is:pr is:open archived:false review-requested:@me")
    my_urls = search("is:pr is:open archived:false author:@me")

    team_prs: list[dict[str, Any]] = []
    for repo in cfg.get("team_repos") or []:
        try:
            rows = gh_json("pr", "list", "-R", repo, "--state", "open", "--limit", "50", "--json", PR_FIELDS)
            team_prs.extend(slim(pr, me) for pr in rows or [])
        except GhError as exc:
            result["errors"].append(str(exc))

    with ThreadPoolExecutor(max_workers=6) as pool:
        result["review_requested"] = [p for p in pool.map(details, requested_urls) if p]
        result["my_prs"] = [p for p in pool.map(details, my_urls) if p]

    seen = {p["url"] for p in result["review_requested"]} | {p["url"] for p in result["my_prs"]}
    result["team_repo_prs"] = [p for p in team_prs if p["url"] not in seen]
    return result
