# Capture: sources and cards

`<since>` and `<since_epoch>` come from `worklog inbox start`. The user's Slack ID is in the Slack search tool
description ("Current logged in user's user_id is …") or `[slack].user_id`. Run the sources in parallel.

## Slack

The connector has no unread state and cannot mark messages as read. "Unread" means: newer than the cursor and not
answered by the user. Use `slack_search_public_and_private` with `after = <since_epoch>` (the Unix timestamp
parameter, not the day filter) and `sort = timestamp`. Page through results until none are left.

1. DMs and group DMs: `channel_types = "im,mpim"`, messages not from the user.
2. Mentions anywhere: keywords `["<@USER_ID>"]`, all channel types.
3. Followed channels: for every channel in `[slack].channels`, filters `in:<channel>`. Keep only threads that ask
   the user something, need their decision, or are addressed to a group the user belongs to and nobody answered.
   Announcements and FYI posts are not inbox items.
4. Saved items (Slack To-dos): filters `is:saved`, no time limit. Every saved item that is not done is a candidate.

Before keeping a message from 1-3, open its thread once (`slack_read_thread`). Drop it when the user replied after
it or added any reaction to it. Several messages in one thread make one candidate: the thread permalink is the key.

## GitHub

`worklog github`:

- `review_requested`: every PR waiting for the user's review (direct or team). Skip drafts unless requested
  directly. Bot PRs are separate cards too.
- `my_prs`: PRs with `review_decision` `CHANGES_REQUESTED`, `ci` `failing`, or waiting for review for more than a day.

The PR URL is the key. A PR is captured once; its card carries the state at capture time.

## Gmail

- `in:inbox category:primary -label:notion`, no time window: read mail that is still in the inbox counts too. For
  Gmail the `notion` label replaces the cursor.
- Keep a thread only when someone asks the user something or needs their action, and the user has not replied later
  in the thread. Skip GitHub, Jira, calendar and other notification mail, newsletters and receipts.
- The thread URL `https://mail.google.com/mail/u/0/#all/<thread id>` is the key.
- After the Notion card is created, add the label `notion` to the thread (create the label first if it does not
  exist). Also label threads skipped because they already have a card in Notion. Change nothing else on the mail:
  read/unread, archive, star and other labels stay.
- If the connector cannot add the label, still create the cards and report it: in the answer and as
  `{"source": "Gmail label", "reason": "…"}` in `missing_sources` of the page JSON. Duplicates are then caught by the
  registry and the URL lookup in Notion.

## Duplicates

1. `worklog inbox check` with the JSON list of candidate URLs: `known` were captured in the last 30 days.
2. For `new`: one `notion-query-data-sources` SQL query on `userDefined:URL` over the whole data source (any status).
   If SQL mode is over its hourly limit, rely on the registry and say so in the answer.

## Card

One card per thread, PR or email.

- Name: an action in English, verb first, with the person and the subject: "Reply to Alice about the API contract",
  "Review org/shop#412 batch processing", "Fix failing CI on Retry policy PR".
- The processing proposes its own action title later (`processing.md`), so a capture title only has to be
  recognisable.
- Status `Inbox`, Category `Work`, URL = the source URL. No Estimate, tags, dates or project: that is processing.
- Body, plain paragraphs:
  - source line: `Slack DM from Alice, 2026-11-23 10:42` / `#team-proj, thread by Bob` / `PR org/shop#412 by alice,
    waiting 26 h` / `Email from Carol <carol@…>, 2026-11-23 09:10`
  - a short verbatim quote (one or two sentences) of the ask
  - the link again
