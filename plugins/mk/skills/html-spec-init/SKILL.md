---
name: html-spec-init
description: Use when setting up a project for HTML specs, or when the user asks to install or update the html-spec skills in a repo - installs the html-spec and html-spec-extract skills into .claude/skills/ so every engineer on the project can use them, and creates .agents/docs/specs, .agents/docs/INDEX.md, local-components.js and a note in CLAUDE.md / AGENTS.md
---

# HTML Spec Init

Prepares a project for planning in HTML specs. The project skills are copied into the repo and committed with it, so every engineer gets them without installing this plugin.

Source files, relative to this skill directory:

- `templates/html-spec/` - planning skill (`SKILL.md`, `template.html`)
- `templates/html-spec-extract/` - rule of three sweep (`SKILL.md`)
- `assets/style.css`, `assets/components.js` - global style and components, published on GitHub Pages at `https://michalkowol.github.io/ai-tools/plugins/mk/skills/html-spec-init/assets/`. Never copy them into the project, specs link to the published URLs.

## What it creates in the project

1. `.claude/skills/html-spec/` - copy of `templates/html-spec/` (invoked as `/html-spec`).
2. `.claude/skills/html-spec-extract/` - copy of `templates/html-spec-extract/` (invoked as `/html-spec-extract`).
3. `.agents/docs/specs/`
4. `.agents/docs/INDEX.md`:

   ```markdown
   # Docs index

   ## Specs

   | Date | Title | Status | File |
   |------|-------|--------|------|
   ```

5. `.agents/docs/specs/local-components.js`:

   ```js
   /*
    * Project-specific components for the specs in this folder.
    * Loaded by every spec after the global components.js.
    *
    * Rule of three: add a component only after the same markup appears
    * at least 3 times across the specs. Prefix elements with local- (never spec-).
    * Use classes and tokens from the global style.css.
    */
   ```

6. A note in the agent instructions file:

   ```markdown
   ## Specs

   Plans and design decisions are kept as HTML specs in `.agents/docs/specs/`, listed in `.agents/docs/INDEX.md`. Before working on a feature, check the index for a related spec and follow its decisions. Create new specs with `/html-spec`, extract repeated markup with `/html-spec-extract`.
   ```

   - If `CLAUDE.md` and/or `AGENTS.md` exist, append the note to each of them.
   - If `CLAUDE.md` only contains `@AGENTS.md`, append the note to `AGENTS.md` only.
   - If neither exists, create `AGENTS.md` with the note and `CLAUDE.md` with the single line `@AGENTS.md`.

## Existing files

Never overwrite silently. For every file that already exists, show what is there (for skills, a diff against the template) and ask the user whether to keep it, merge, or overwrite it. Ask about each file separately. A file that already matches needs no question, just report it.

Re-running the init is how a project picks up a newer version of the skills.

## Report

At the end list what was created, updated, merged and left unchanged, and remind the user to commit `.claude/skills/` and `.agents/docs/`.
