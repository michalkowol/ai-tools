---
name: ai-slop-remove
description: Remove AI slop from text - strip LLM writing tells (em dashes, "not X but Y", rule of three, delve/crucial/tapestry, sycophantic openers, closing offers, fake headers, bold-first bullets, padding) and rewrite it plainly in the author's voice. Use when the user asks to de-slop, humanize, make text sound less like AI or ChatGPT, or clean up an AI-drafted post, email, doc, PR description or Slack message. Also apply as a final pass to your own drafts when asked.
argument-hint: "[text] [--audit] [--keep-format]"
---

# AI Slop Remover

Rewrite the input so it reads like a competent human wrote it on purpose: shorter, specific, direct, with no LLM tells. Keep every fact, number, name and the author's actual opinion. Keep the original language (Polish stays Polish).

Removing tells is not the goal; saying something is. Deleting phrases only produces disguised slop ("rather than X, Y" instead of "not X, but Y"). Ban the rhetorical move, not the wording.

## Modes

- default: output the cleaned text only.
- `--audit`: first list the tells found (quote + category), then the cleaned text, then one line with word count before -> after.
- `--keep-format`: keep the existing headers and lists, only clean the prose inside them.

## Pass 1: cut what carries no information

Delete outright:

- Sycophantic openers: "Great question!", "Certainly!", "Absolutely!", "I'd be happy to help", "What a fascinating...".
- Preambles that announce instead of answer: "There are several factors to consider", "Let's dive in", "Let's break this down", "Here's what you need to know".
- Restating the question; the tie-back "So, to answer your question...".
- Closing offers and wishes: "I hope this helps!", "Let me know if you have any questions", "Would you like me to...?", "Feel free to reach out", "I hope this email finds you well".
- Signposted conclusions and recaps that repeat the body: "In conclusion", "In summary", "Ultimately", "At the end of the day", "Key Takeaways", "Final Thoughts". If a recap is genuinely needed (long doc), keep one, at the top, as a TL;DR.
- Fractal summaries: summaries after every section.
- Filler transitions: "It's worth noting that", "Notably", "Importantly", "Moreover", "Furthermore", "Additionally" (keep a connector only when it expresses a real logical relation, then prefer "and", "but", "so", "because").
- Belabouring the obvious: "To be clear, this isn't a criticism...", objections nobody raised.
- False suspense: "Here's the thing:", "Here's the kicker:", "And that's where it gets interesting."
- "-ing" significance tails: ", highlighting the importance of...", ", fostering a culture of...", ", underscoring...".
- Knowledge-cutoff and AI disclaimers, leftover placeholders like "[Company Name]".
- Restatements: when one point is made in several ways, keep the best one.

## Pass 2: fix the moves

- Negative parallelism ("It's not X, it's Y", "not just X but Y", "This isn't about X - it's about Y", "Not X. Not Y. Just Z."): state Y directly. Mention X only if someone actually believes X, and then say who.
- Rule of three: keep the items that are true and distinct. Two or four is fine. One is often best.
- Rhetorical question answered immediately ("The result? Chaos."): write the statement ("It caused chaos.").
- Grandiose stakes: scale the claim to what the facts support. A config change is a config change.
- Vague attributions ("experts agree", "studies show", "many believe"): name the source, or own the claim ("I think"), or delete it. Never invent a source.
- Quotable one-liners and invented Capitalised Concepts: replace with the concrete point, or delete.
- "Think of it as...", "Imagine a world where...": cut unless the analogy explains something non-obvious to this audience.
- "From X to Y" false ranges: list what you actually mean.
- "Despite its challenges, X continues to thrive": name the challenge and the actual outcome.
- Hedging stacks ("may potentially", "can often help to"): one hedge where uncertainty is real, none elsewhere.
- False vulnerability ("I'll be honest..."): delete the frame, keep the content.
- Collaborative "we" in single-author text: use "I" or the actual actor.

## Pass 3: fix the words

- Copula avoidance: "serves as", "stands as", "represents", "boasts", "features" -> "is", "has".
- Inflated vocabulary -> plain words: delve -> look at / cover; leverage / harness / utilize -> use; foster -> build / encourage; navigate -> handle; showcase -> show; underscore -> show; embark -> start; streamline -> simplify; crucial / pivotal / vital -> important (or say why it matters); robust -> reliable (or the actual property); seamless -> say what does not break; landscape / realm / tapestry / ecosystem / journey -> the concrete thing, or delete.
- Magic adverbs: quietly, deeply, fundamentally, remarkably, truly, seamlessly, incredibly - delete.
- Synonym cycling: pick one name for a thing and reuse it.
- Polish: "W dzisiejszym dynamicznym świecie" -> delete; "kluczowy / istotny" -> "ważny" or the reason; "stanowi" -> "jest"; "warto zauważyć, że" -> delete; "odgrywa kluczową rolę w" -> say what it does; "nie tylko..., ale także" -> "i" or two sentences; "zanurzmy się", "podsumowując", "mam nadzieję, że to pomoże" -> delete.

## Pass 4: fix the formatting

- Em dashes (—) and spaced en dashes (–): replace with a comma, colon, parentheses, full stop or plain hyphen. Target zero.
- Headers: remove them from anything shorter than ~300 words, from emails and chat messages. Elsewhere use sentence case and descriptive headers, not "Why It Matters" / "The Bottom Line".
- Bullet lists: turn into a sentence when there are fewer than three items or the items form one thought. Keep lists for genuinely parallel, scannable items (steps, options, specs).
- Bold-first bullets and mid-sentence bold: remove; bold at most one thing the reader must not miss.
- Emoji (✅ ❌ 🚀 💡 👉 🔥 1️⃣) and Unicode decoration (→ ≈ ⚠️ ─, curly quotes): remove or use plain ASCII, unless the user's own text used them.
- Markdown in a medium that will not render it (email, plain-text chat): convert to plain text.
- Title Case Headings: sentence case.
- Stacked one-line paragraphs: merge into normal paragraphs. Vary sentence length naturally.

## Pass 5: make it specific

Slop is generic. After cleaning, check every remaining sentence: could it appear unchanged in a text about a different topic? If yes, replace it with the concrete detail from the input (the number, the name, the date, the example) or delete it. Do not invent details that are not in the input; if the text becomes very short, that is the correct result.

## Guardrails

- One isolated instance of a pattern is not slop; clusters are. Do not mangle a legitimate list, a real contrast ("not Postgres but MySQL, because...") or a quote.
- Do not add new tells while removing old ones (no "rather than X, Y", no colon-reveal "The answer: Y" as a disguised parallelism).
- Do not swap the author's opinion for a neutral one, and do not soften blunt statements.
- Respect the user's own style rules if they exist (e.g. no em dashes, no Oxford comma, soft-wrapped Markdown).
- Final check: read the result once more looking only for em dashes, "not X but Y", triads, the banned vocabulary and a closing offer. Fix any that slipped through.
