---
name: init
description: Use when setting up a project for HTML specs, or when the user asks to install, update or upgrade the html-spec skills in a repo - installs the html-spec and html-spec-extract skills into .claude/skills/ so every engineer on the project can use them, copies style.css and global-components.js, creates .agents/docs/specs, .agents/docs/specs/assets, .agents/docs/INDEX.md, local-components.js and a note in CLAUDE.md / AGENTS.md, and on re-run upgrades them and migrates existing specs to the current format
---

# HTML Spec Init

Prepares a project for planning in HTML specs. The project skills are copied into the repo and committed with it, so every engineer gets them without installing this plugin.

Source files, relative to this skill directory:

- `templates/html-spec/` - planning skill (`SKILL.md`, `template.html`)
- `templates/html-spec-extract/` - rule of three sweep (`SKILL.md`)
- `assets/style.css`, `assets/global-components.js` - global style and components. The header of both holds the current spec format (`html-spec format N`).
- `MIGRATIONS.md` - how to migrate specs from an older format.

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

5. `.agents/docs/specs/assets/` with `style.css` and `global-components.js` - copies of `assets/`. Specs link them with relative paths (`assets/style.css`). The folder keeps the specs folder for specs only.
6. `.agents/docs/specs/assets/local-components.js`:

   ```js
   /*
    * Project-specific components for the specs in this folder.
    * Loaded by every spec after global-components.js.
    *
    * Rule of three: add a component only after the same markup appears
    * at least 3 times across the specs. Prefix elements with local- (never spec-).
    * Use classes and tokens from the global style.css.
    */
   ```

7. A note in the agent instructions file:

   ```markdown
   ## Specs

   Plans and design decisions are kept as HTML specs in `.agents/docs/specs/`, listed in `.agents/docs/INDEX.md`. Before working on a feature, check the index for a related spec and follow its decisions. Create new specs with `/html-spec`, extract repeated markup with `/html-spec-extract`.
   ```

   - If `CLAUDE.md` and/or `AGENTS.md` exist, append the note to each of them.
   - If `CLAUDE.md` only contains `@AGENTS.md`, append the note to `AGENTS.md` only.
   - If neither exists, create only `AGENTS.md` with the note. Claude Code reads `AGENTS.md` when there is no `CLAUDE.md`.

## Existing files

Never overwrite silently. For every file that already exists, show what is there (for skills, a diff against the template) and ask the user whether to keep it, merge, or overwrite it. Ask about each file separately. A file that already matches needs no question, just report it.

Exception: `style.css` and `global-components.js` in `.agents/docs/specs/assets/` are owned by the plugin. Replace them with the current version without asking about each file, and report the format change (e.g. "format 1 → 2"). If a copy differs from `assets/` in a way that looks like a local edit (not just an older version), show the diff and ask before replacing; suggest moving the edit to `local-components.js` or to the plugin.

## Upgrade

Re-running the init is how a project picks up a newer version. Besides updating the skills and the assets:

1. Find the project's current format: the `html-spec format N` header in `.agents/docs/specs/assets/global-components.js`.
2. Read every `.agents/docs/specs/*.html` and its format: `<meta name="html-spec" content="N">`. A spec without the tag was not created from the template: show it to the user instead of migrating it.
3. For every spec below the current format, plan the steps from `MIGRATIONS.md`, in order. Show the user the list of specs with their format and what would change (one before / after example per kind of change).
4. Wait for approval, then apply. Migrate all specs, including `decided` and `implemented` ones. Change structure only, never content, language, decisions or status.
5. Open one migrated spec in a browser if possible, or at least check that every spec links `assets/style.css`, `assets/global-components.js` and `assets/local-components.js` and that the files exist.

## Report

At the end list what was created, updated, merged and left unchanged, the format change and the migrated specs, and remind the user to commit `.claude/skills/` and `.agents/docs/`.
