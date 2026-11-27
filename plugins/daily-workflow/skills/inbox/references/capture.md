# Capture: sources and cards

`<since>`, `<since_epoch>` and `<todos_after>` come from `worklog inbox start`. The user's Slack ID is in the Slack
search tool description ("Current logged in user's user_id is …") or `[slack].user_id`. Run the sources in parallel.

## Slack

The connector has no unread state and cannot mark messages as read. "Unread" means: newer than the cursor and not
answered by the user. Use `slack_search_public_and_private` with `after = <since_epoch>` (the Unix timestamp
parameter, not the day filter) and `sort = timestamp`. Page through results until none are left.

1. DMs and group DMs: `channel_types = "im,mpim"`, messages not from the user.
2. Mentions anywhere: keywords `["<@USER_ID>"]`, all channel types.
3. Followed channels: for every channel in `[slack].channels`, filters `in:<channel>`. Keep only threads that ask
   the user something, need their decision, or are addressed to a group the user belongs to and nobody answered.
   Announcements and FYI posts are not inbox items.
4. Slack To-dos: filters `is:todos after:<todos_after>`, without the `after` timestamp parameter: the to-dos whose
   message is at most 30 days old, whatever the cursor says. Older to-dos stay in Slack; the `knowledge` mode
   reads all of them.

Before keeping a message from 1-3, open its thread once (`slack_read_thread`). Drop it when the user replied after
it or added any reaction to it. Several messages in one thread make one candidate: the thread permalink is the key.

To-dos (4):

- Every to-do in the window is a candidate, also when it asks nothing of the user: an article, a recording or a
  piece of information the user saved. Processing decides what it is.
- The key is the permalink the search returns for the saved message. A to-do in a thread that is already a
  candidate from 1-3 is the same candidate.
- The search returns completed to-dos too and cannot filter by state. Drop a to-do only when its thread shows that
  the user already dealt with it (their later reply closes the ask).
- Spell the filter exactly `is:todos`. Slack silently ignores a modifier it does not know and then returns the
  newest messages of the whole workspace; if the results are clearly not the user's saved messages, report the
  source as failed instead of capturing them. To-dos typed by hand without a message are not returned.
- `worklog inbox check` lists under `knowledge` the URLs that the knowledge base already stores as knowledge
  (`knowledge.md`): such a to-do gets no card. A to-do the base lists as a request still gets one.

## GitHub

`worklog github`:

- `review_requested`: every PR waiting for the user's review (direct or team). Skip drafts unless requested
  directly. Bot PRs are separate cards too.
- Small PRs: skip every `review_requested` PR with `size.small` (fewer than 10 changed files), always, also on a
  direct request. The user's recurring code review card (it links to `github.com/pulls/reviews`) covers them. Do not
  record their URLs, so a PR that grows past the threshold gets a card in a later capture, and never change the
  recurring card. Count them for the answer: "N small PRs left for the code review card".
- `my_prs`: PRs with `review_decision` `CHANGES_REQUESTED`, `ci` `failing`, or waiting for review for more than a day. Own PRs
  always get a card, whatever their size.

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

1. `worklog inbox check` with the JSON list of candidate URLs: `known` were captured in the last 30 days,
   `knowledge` are stored as knowledge in the knowledge base (only to-dos are dropped for that).
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
  - source line: `Slack DM from Alice, 2026-11-23 10:42` / `#team-proj, thread by Bob` / `Slack to-do: #team-proj,
    message by Bob, 2026-11-20` / `PR org/shop#412 by alice, waiting 26 h, 7 files (+120/−30)` (PRs always end with
    the size from `size`) / `Email from Carol <carol@…>, 2026-11-23 09:10`
  - a short verbatim quote (one or two sentences) of the ask; for a to-do that asks nothing, of what it says
  - the link again, and for a to-do the links from the message
- A to-do that is not a request gets a title that names it instead of an action: "Article: retry patterns for event
  consumers", "Note: staging deploys are frozen until Monday".
