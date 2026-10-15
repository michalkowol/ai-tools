---
name: pr-review-comments
description: Use when adding inline review comments to a GitHub pull request - creates a PENDING review in plain English with no general review comment
argument-hint: "<PR number or URL> [what to comment on]"
---

Add inline comments to a GitHub PR as a **pending** review. The user publishes it later in the GitHub UI with "Finish your review".

## Rules

- **Never add a general review comment.** No `body` and no `event` in the payload. A general comment cannot be deleted later, inline comments can.
- Keep the review pending. Do not submit, approve or request changes.
- Write in plain, simple English: short sentences, common words, no jargon when a simple word works.
- One point per comment. Say what you see, why it matters and ask a question or suggest a fix.
- Never use an em dash or en dash. Use a plain hyphen or rephrase.
- Never use the Oxford comma.
- No emojis, no greetings, no "nit:" unless the user asks.
- If the user already picked the points, comment only on those. Otherwise propose the list first and wait for the user to choose.

## Steps

1. Get PR data: `gh pr view <N> --json headRefOid,headRefName,baseRefName,files,title`. Use `headRefOid` as `commit_id`.
2. Read the diff (`git diff <base>...<head>` or `gh pr diff <N>`) and find the exact line numbers in the **new** file version.
3. Check every line is inside a diff hunk (added or context line). GitHub rejects comments on lines outside the diff.
4. Write the payload to the scratchpad, for example `review_<N>.json`:

   ```json
   {
     "commit_id": "<headRefOid>",
     "comments": [
       {"path": "path/to/File.java", "line": 42, "side": "RIGHT", "body": "..."}
     ]
   }
   ```

   For a range use `start_line` + `line` (both with `side: "RIGHT"`).
5. `gh api` is blocked by the mk guard hook, so do not run it and do not route around it with curl. Ask the user to run:

   ```
   ! gh api -X POST repos/<OWNER>/<REPO>/pulls/<N>/reviews --input <payload path>
   ```

6. After the user runs it, confirm `"state":"PENDING"` and `"body":""` in the output and give the `html_url`.

## Gotchas

- Only one pending review per account per PR. If one already exists, the POST fails. Ask the user to publish it first or add the comment by hand in the UI.
- A pending review is visible only to its author. Check which account `gh auth status` uses and tell the user if it may not be their main account.
- Show the user the final comment texts in the reply so they can review them before running the command.
