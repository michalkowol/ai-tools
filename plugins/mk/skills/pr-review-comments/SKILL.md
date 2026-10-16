---
name: pr-review-comments
description: Use when adding inline review comments to a GitHub pull request, including turning local uncommitted edits into "Apply suggestion" comments - creates a PENDING review in plain English with no general review comment
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

1. Get PR data: `gh pr view <N> --json headRefOid,headRefName,baseRefName,files,title,url`. Use `headRefOid` as `commit_id`.
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

## Suggestions from local edits

Use this when the user (or you) edited files on the PR branch and wants the edits as one-click "Apply suggestion" comments instead of commits. Idea from [kjkrol/gh-suggest](https://github.com/kjkrol/gh-suggest).

1. Local `HEAD` must equal `headRefOid` and the edits must stay uncommitted, otherwise line numbers do not match. Get there with `gh pr checkout <N>`. Make sure the working tree has no unrelated edits or untracked files, every hunk and every new file becomes a comment. If an untracked file looks like a local artifact (logs, build output, IDE files), ask before including it.
2. Read the edits with `git diff -U0 HEAD`. Each `@@ -a,b +c,d @@` hunk replaces old lines `a` to `a+b-1`, which are the PR head lines. List new files with `git ls-files --others --exclude-standard` and read them in full, they are not in `git diff`.
3. Read the commentable ranges from `gh pr diff <N>`: each `+c,d` in a hunk header (with `d > 0`) allows comments on lines `c` to `c+d-1`.
4. Turn every local hunk into one comment:
   - **Fully inside a commentable range**: `start_line` = `a`, `line` = `a+b-1` (just `line` for one line) and the body is a suggestion block with the new lines exactly as in the diff, indentation included:

     ````
     ```suggestion
     <added lines>
     ```
     ````

     A pure deletion is an empty suggestion block. A pure insertion (`b` = 0) must replace an existing line, so anchor it on line `a` and put that line first in the block, followed by the inserted lines (for `a` = 0 anchor on line 1 and put the inserted lines before it).
   - **Partly inside**: anchor on the overlapping lines and put the full change in a ` ```diff ` block, saying it covers lines `a` to `a+b-1` and cannot be a one-click suggestion.
   - **Outside the diff**: anchor on the nearest commentable line in the same file. Put a permalink `https://github.com/<OWNER>/<REPO>/blob/<headRefOid>/<path>#L<a>-L<end>` on its own line (GitHub renders the snippet) and the change as a ` ```diff ` block. If the file is not in the PR at all, treat it like a new file below.
   - **New (untracked) file**: it does not exist in the PR, so GitHub cannot show a suggestion for it. Anchor one comment on the most related commentable line (for example where the new file is used or should be used) and propose the file there: its path, then the full content in a fenced block with the language of the file. Use a fence longer than any backtick run inside the file. If no line is clearly related, ask the user where to put it.
5. Do not add prose to suggestion bodies unless the user asks. Continue with steps 4 to 6 above.
6. Ask before reverting the local edits (`git restore <files>`). Never discard them on your own.

## Gotchas

- Only one pending review per account per PR. If one already exists, the POST fails. Ask the user to publish it first or add the comment by hand in the UI.
- A pending review is visible only to its author. Check which account `gh auth status` uses and tell the user if it may not be their main account.
- Show the user the final comment texts in the reply so they can review them before running the command.
