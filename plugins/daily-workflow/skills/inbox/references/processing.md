# Processing: page JSON and applying answers

## Page JSON (`~/.ai/worklog/inbox/YYYY-MM-DD-HHMM.json`)

`worklog render-inbox <file>` renders it into a fixed page next to it. All text is plain text, the renderer escapes
it and keeps only `http(s)` links. The renderer orders the cards, so their order in the file does not matter.

```json
{
  "v": 1,
  "date": "2026-11-23",
  "generated_at": "2026-11-23T09:31:04+01:00",
  "captured": {"created": 7, "skipped": 3},
  "projects": ["Platform migration", "Hiring"],
  "agenda_cards": [{"id": "notion-page-id", "name": "Alice"}],
  "cards": [
    {
      "id": "notion-page-id",
      "url": "https://www.notion.so/…",
      "title": "Reply to Alice about the API contract",
      "source": {"label": "Slack DM from Alice", "url": "https://….slack.com/archives/…"},
      "quote": "Can you confirm the contract by Wednesday?",
      "age": "2 h",
      "created_at": "2026-11-23T07:12:00+01:00",
      "waiting_on_me": true,
      "proposal": {
        "outcome": "next",
        "title": "Confirm the API contract with Alice",
        "category": ["Work"],
        "estimate": "0.5 x 🍅",
        "priority": "P1",
        "reminder": "2026-11-23",
        "due": "2026-11-25",
        "project": "",
        "agenda": "",
        "why": "Direct ask with a Wednesday deadline."
      },
      "result": ""
    }
  ],
  "missing_sources": [{"source": "Gmail", "reason": "connector not signed in"}]
}
```

- `waiting_on_me`: someone is blocked on the user (a direct question, a review request, a requested change). These
  cards go first, then cards with a due date, then the rest oldest first (`created_at`).
- `source` and `quote`: from the card body; for cards added by hand, the URL field if any, otherwise omit.
- `result`: empty until `apply`, then e.g. `applied: Next Actions`, `failed: <reason>`, `delete by hand`.

## Proposal rules

| Outcome | When | Notion change |
|---|---|---|
| `done` | takes under two minutes and the user can do it right now (a short reply, an approval) | Status `Done (today)` |
| `next` | the user has to do it | Status `Next Actions`, Reminder on the planned day |
| `waiting` | the next step is someone else's | Status `Waiting for`, Reminder = the follow-up day |
| `agenda` | a topic to raise with one person who has an Agenda card | append to that card, archive this one |
| `someday` | maybe later, no commitment | Status `Someday/Maybe` |
| `icebox` | parked, keep for reference | Status `Icebox` |
| `trash` | no action and nothing to keep (FYI, already handled, noise) | archive the page |
| `keep` | not enough information to decide | no change, stays in the Inbox |

- Estimate and priority as in `gtd-rules.md`: light ≤ 1 x 🍅, heavy ≥ 2 x 🍅, `None` for work tracked in Jira and for
  Agenda; one of P1, P2, P3. Reviews are usually light, P1 when the author is blocked.
- Reminder: today for blocking items, otherwise the day it makes sense; never in the past. Due Date only for a real
  deadline stated in the source.
- Category: `Work` for captured cards; for cards added by hand judge from the content (`Home`, or both).
- Project only from `projects`, empty when nothing fits.
- Title: propose an action title (verb first) when the current one is vague, a bare link, or holds two actions;
  otherwise repeat the current title.

## Apply

Each pasted line is `{"id": …, "outcome": …, <shown fields>, "note": …}`. Only the fields the page shows for the
outcome are present. Look up the card by `id` in the page JSON, ignore unknown ids.

- `done`, `next`, `waiting`, `someday`, `icebox`: `notion-update-page` on the card: Name = `title` if it changed,
  Status per the table above, Category, Estimate, Tags = the priority plus the card's existing ♻️ Recurring tag if it
  has one, Reminder, Due Date, Project. Empty fields are cleared only for Reminder and Due Date when the outcome sets
  them; other empty fields are left as they are.
- `agenda`: append one bullet to the body of the Agenda card named in `agenda`: the card title, the note if any, and
  the link to the source (or the card). Then archive the Inbox card.
- `trash`: move the page to trash with the Notion tool that supports it. If no tool can archive or trash a page, set
  Status `Done` and report it as "delete by hand".
- `note`: the user's correction or context. Apply it on top of the fields (e.g. "ask Bob instead" → adjust the title).
  If the note contradicts the outcome, apply nothing for that card and report it.
- After every line, set the card's `result` in the page JSON, then re-render once at the end.
