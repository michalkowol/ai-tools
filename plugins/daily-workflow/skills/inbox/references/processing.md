# Processing: page JSON, proposal and apply

## Page JSON (`~/.ai/worklog/inbox/YYYY-MM-DD-HHMM.json`)

The JSON is the source of truth for apply. `worklog render-inbox <file>` turns it into declarative markup next to it
(`<inbox-app>`, `<inbox-entry>`, `<inbox-card>`) and copies the components from the plugin into `inbox/assets/`. All
text is plain text: the renderer escapes it and keeps only `http(s)` links. The renderer orders the entries, so their
order in the file does not matter.

```json
{
  "v": 2,
  "date": "2026-11-23",
  "generated_at": "2026-11-23T09:31:04+01:00",
  "captured": {"created": 7, "skipped": 3},
  "agenda_cards": [{"id": "notion-page-id", "name": "Alice"}],
  "entries": [
    {
      "id": "notion-page-id",
      "url": "https://www.notion.so/…",
      "title": "Review org/shop#412 PROJ-1234: Batch processing for events",
      "source": {"label": "PR org/shop#412 by alice", "url": "https://github.com/org/shop/pull/412"},
      "age": "4 d",
      "created_at": "2026-11-19T10:00:00+01:00",
      "waiting_on_me": true,
      "why": "Review required and nobody approved yet; Alice waits 4 days.",
      "cards": [
        {"outcome": "next", "title": "Review Alice's batch processing (shop#412)", "category": ["Work"],
         "estimate": "1 x 🍅", "priority": "P1", "reminder": "2026-11-23", "due": "", "project": "", "agenda": ""}
      ],
      "result": ""
    }
  ],
  "missing_sources": [{"source": "Gmail", "reason": "connector not signed in"}]
}
```

- `title`: the current Notion title, shown as "Original: …". `url`: the Notion page. `source`: from the URL field and
  the card body; `null` for entries added by hand.
- `cards`: the proposal, at least one. Card 1 is always the original page, the others become new cards. Every card has
  a `title`, Trash and Keep too; if card 1 has none, the renderer shows the original title.
- `waiting_on_me`: someone is blocked on the user (a direct question, a review request, a requested change). These
  entries go first, then entries whose first card has a due date, then the rest oldest first (`created_at`).
- `why`: one line for the whole entry; for a split it says why.
- `result`: empty until `apply`, then e.g. `applied: Next Actions + 1 created`, `failed: <reason>`.
- The old format (top-level `cards` with one `proposal` each) is rejected; run `process` again.

## Proposal rules

| Outcome | When | Notion change |
|---|---|---|
| `done` | takes under two minutes and the user can do it right now (a short reply, an approval) | Status `Done (today)` |
| `next` | the user has to do it | Status `Next Actions`, Reminder on the planned day |
| `waiting` | the next step is someone else's | Status `Waiting for`, Reminder = the follow-up day |
| `agenda` | a topic to raise with one person who has an Agenda card | append to that card, trash this one |
| `someday` | maybe later, no commitment | Status `Someday/Maybe` |
| `icebox` | parked, keep for reference | Status `Icebox` |
| `trash` | no action and nothing to keep (FYI, already handled, noise) | move the page to Trash |
| `keep` | not enough information to decide | no change, stays in the Inbox |

- Title: always propose an action title for every card, Trash and Keep included (the page shows it, struck
  through for Trash, and it is ready when the user switches the status), not only when the current one is vague: verb first, what and for whom,
  about 60 characters, the PR reference in parentheses, e.g. `Review Alice's batch processing (shop#412)`,
  `Approve vitest security bump (web#175)`.
- Title language follows the entry: captured entries in English; entries the user added by hand in another language
  keep it (e.g. a Polish card gets a Polish action title).
- Split: when the title or body holds several independent actions, one card per action. Card 1 is the main action.
- Estimate and priority as in `gtd-rules.md`: light ≤ 1 x 🍅, heavy ≥ 2 x 🍅, `None` for work tracked in Jira and for
  Agenda; one of P1, P2, P3. P1 for a review when the author is blocked.
- PR estimate from the changed files in the source line (`7 files (+120/−30)`): 1–3 files 0.25 x 🍅, 4–9 0.5 x 🍅,
  10–19 1 x 🍅, 20–39 2 x 🍅, 40+ 3 x 🍅. Without a file count, open the PR size with `worklog github` only if the PR
  is still listed there, otherwise estimate as usual.
- Small review PR (someone else's PR waiting for the user's review, fewer than 10 files): propose `trash` with the
  reason "small PR, covered by the code review card". Own PRs (the user is the author) are never trashed by this rule.
- Reminder: today for blocking items, otherwise the day it makes sense, never in the past. Due Date only for a real
  deadline stated in the source.
- Category: `Work` for captured entries; for entries added by hand judge from the content (`Home`, or both).
- Project only from existing options, empty when nothing fits. The page shows it read-only; the user changes it
  through the note.
- Agenda: `agenda` is the exact name of an Agenda card from `agenda_cards`, or empty when unsure.

## Fields per status

The page shows, and the apply line carries, only these fields (plus `title`, except for Trash and Keep):

| Status | Fields |
|---|---|
| `done` | category, estimate, priority, reminder, due |
| `next` | category, estimate, priority, reminder, due, project |
| `waiting` | category, priority, reminder, due, project |
| `agenda` | agenda |
| `someday`, `icebox` | category, reminder, due, project |
| `trash`, `keep` | none |

## Apply

The prompt from the page: `/daily-workflow:inbox apply <file>`, then one line per entry with at least one non-Keep
card. Look up the entry by `id` in the page JSON, ignore unknown ids.

```json
{"id": "<page id>", "outcome": "next", "title": "…", "category": ["Work"], "estimate": "1 x 🍅", "priority": "P1", "reminder": "2026-11-23", "due": "", "project": "", "note": ""}
{"id": "<page id>", "cards": [{"outcome": "keep"}, {"outcome": "next", "title": "…", "category": ["Home"], "…": "…"}], "note": "shared note"}
```

- Single card: apply it to the original page. Split (`cards`): card 1 applies to the original page, every other card
  is created with `notion-create-pages` in the data source: Name, Status per the table above, the fields of the line,
  Category, the URL copied from the original, and a body with a link back to the original card. A card
  `{"outcome": "keep"}` changes nothing: in place 1 the original stays in the Inbox, elsewhere no card is created.
- Properties (`notion-update-page`, `update_properties`): Name = `title`, Status, Category, Estimate,
  Tags = the priority plus the card's existing ♻️ Recurring tag if it has one, Reminder, Due Date, Project. Empty
  `reminder` / `due` clear the date; never fill an empty date with a default. Fields missing from the line stay as
  they are.
- Title changed: append a line `Original title: <old title>` to the page body.
- The body: only append (`insert_content` at the end), never `replace_content` or rewrite. The user's notes, the
  captured source line, quote and link always stay.
- `agenda`: append one bullet to the body of the Agenda card named in `agenda` (the card title, the note if any, a
  link to the source or the card), then move the Inbox card to Trash. Empty `agenda`: skip the card and report it.
- `trash`: `notion-delete-pages` with `user_confirmed: true` (the pasted line is the user's explicit request); the page
  can be restored from Trash.
- `note`: a correction or context for every card of the entry (e.g. "project Hiring", "no project", "this is about
  PROJ-1234"). Apply it on top of the fields. If it contradicts the fields, apply nothing for that entry and report it.
- After every line, set the entry's `result` in the page JSON, then re-render once at the end.
