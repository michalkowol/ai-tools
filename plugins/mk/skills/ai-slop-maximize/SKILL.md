---
name: ai-slop-maximize
description: Rewrite or generate text as maximal AI slop - every known LLM writing tell stacked on purpose. Use when the user asks to "slopify", make text sound as AI-generated as possible, parody ChatGPT/LinkedIn style, or produce test data for an AI-slop detector or for the ai-slop-remove skill.
argument-hint: "[text or topic] [--level 1-3] [--genre linkedin|blog|email|wiki|chat]"
---

# AI Slop Maximizer

Turn the input (a text to rewrite, or a topic to write about) into the most recognisably AI-generated prose possible. This is deliberate parody: the goal is that any reader, detector or the `ai-slop-remove` skill flags it instantly.

Keep the original facts and the original language (Polish stays Polish, English stays English). Slop is about form and padding, not about inventing new facts - except vague attributions ("experts agree"), which are part of the genre.

## Levels

- `--level 1` light: 5-8 tells, still readable, "a slightly too polished ChatGPT answer".
- `--level 2` (default): 15+ tells, every paragraph carries at least three.
- `--level 3` unhinged: every tell in the catalogue at least once, word count tripled, summaries of summaries.

## Genres

Pick from `--genre` or infer from the input. Each genre has its own skeleton:

- `chat`: "Great question!" -> restated question -> bolded headers -> bullet list -> "In summary" -> "I hope this helps! Would you like me to...?"
- `linkedin`: one-line hook -> "Here's the thing." -> stacked one-sentence paragraphs -> "Not X. Not Y. Just Z." -> lesson in three bullets with ✅ -> question to the audience -> "Agree? 👇" -> hashtags.
- `blog`: "In today's fast-paced digital landscape..." -> "Let's dive in." -> Title Case H2s ("Why It Matters", "The Bottom Line") -> bold-first bullets -> "In conclusion".
- `email`: "I hope this email finds you well." -> "I wanted to reach out" -> "circle back" -> "Please don't hesitate to reach out" -> "Best regards".
- `wiki`: "X stands as a testament to..." -> "-ing" significance clauses -> "Despite its challenges, X continues to thrive" -> "Legacy" section.

## Catalogue of tells to inject

### Openers and closers (chatbot artifacts)
- Sycophantic opener: "Great question!", "Certainly! Here's...", "Absolutely!", "I'd be happy to help!", "What a fascinating topic!"
- Announce-then-answer preamble: "There are several key factors to consider here."
- Restating the question before answering.
- Closing offer: "I hope this helps!", "Let me know if you'd like me to expand on any of these points!", "Would you like me to create a checklist?"
- Signposted conclusion: "In conclusion", "In summary", "Ultimately", "At the end of the day", "The bottom line?"
- Tie-back: "So, to answer your question: yes."

### Vocabulary
- Grand nouns: tapestry, landscape, realm, paradigm, synergy, journey, ecosystem, testament, cornerstone, game-changer, beacon.
- Verbs: delve, leverage, harness, navigate, foster, unlock, elevate, empower, streamline, underscore, showcase, embark.
- Adjectives: crucial, pivotal, vital, robust, seamless, intricate, vibrant, multifaceted, transformative, ever-evolving, cutting-edge, nuanced.
- Magic adverbs: quietly, deeply, fundamentally, remarkably, truly, seamlessly, arguably.
- Filler transitions: "It's worth noting that", "Notably", "Moreover", "Furthermore", "Additionally", "Importantly", "Crucially".
- Copula avoidance: never "is" or "has" - always "serves as", "stands as", "boasts", "features", "represents", "marks".
- Synonym cycling: the platform... the solution... the tool... the ecosystem (same thing, four names).
- Polish equivalents: "W dzisiejszym dynamicznie zmieniającym się świecie", "kluczowy", "istotny", "warto zauważyć, że", "nie tylko..., ale także", "odgrywa kluczową rolę", "stanowi" zamiast "jest", "w erze cyfrowej", "zanurzmy się", "podsumowując", "mam nadzieję, że to pomoże!".

### Rhetorical moves
- Negative parallelism, as often as possible: "It's not just X, it's Y", "This isn't about X - it's about Y", "not because X, but because Y".
- Countdown reveal: "Not X. Not Y. Just Z."
- Rule of three, chained: "fast, reliable and scalable", then another triad in the next sentence.
- Rhetorical question answered immediately: "The result? Chaos."
- False suspense: "But here's the kicker:", "Here's the thing:", "And that's where it gets interesting."
- Grandiose stakes: a config change "redefines the future of how teams collaborate".
- "-ing" significance tails: "..., highlighting the importance of collaboration and fostering a culture of innovation."
- Vague attributions: "Experts agree", "Studies show", "Industry observers note", "Many believe".
- Quotable one-liners that mean nothing: "Speed without direction is just motion."
- Invented concept labels with capital letters: "the Alignment Gap", "the Velocity Paradox".
- "Think of it as..." analogy for something trivial; "Imagine a world where...".
- "From X to Y" false ranges: "from startups to enterprises, from code to culture".
- "Despite its challenges, X continues to thrive."
- Belabouring the obvious: "To be clear, this is not a criticism of anyone."
- False vulnerability: "I'll be honest - I was skeptical at first."
- Hedging stack: "may potentially", "can often help to", "in many cases, though not always".

### Structure
- Fractal summaries: summary at the top, after each section and at the end.
- One point restated in five ways to pad length.
- Compulsive counting: "Here are 5 key reasons why this matters:".
- Stacked one-sentence paragraphs for fake punch.
- Anaphora: "They built... They built... They built...".
- Uniform sentence length (low burstiness), except for the punchy fragments.

### Formatting
- Em dashes everywhere - several per paragraph - including where a comma would do.
- Title Case Headings With "Why It Matters", "Key Takeaways", "The Bottom Line", "Final Thoughts".
- Bold-first bullets: "**Scalability:** ...". Excessive **bold** mid-sentence.
- Bullet lists where one sentence would do.
- Emoji as bullets: ✅ ❌ 🚀 💡 👉 🔥 and keycap digits 1️⃣ 2️⃣ 3️⃣.
- Unicode decoration: arrows (Input → Process → Output), ≈, ⚠️, curly quotes, horizontal rules `---`.
- Markdown in contexts that do not render it (emails, chat messages).

## Procedure

1. Extract the facts and the core point of the input. Note the language.
2. Choose genre and level.
3. Build the genre skeleton, then expand every fact into a paragraph using the catalogue. Prefer stacking several tells in one sentence: "It's worth noting that this isn't just a tool - it's a testament to the transformative power of seamless collaboration."
4. Check coverage: count the distinct tells used and make sure the level target is met. Make sure em dashes, negative parallelism, rule of three and the closing offer are always present - these are the most recognised tells.
5. Output only the slop text. If the user asked for it, append a short "Tells used" list after a separator.
