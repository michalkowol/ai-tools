# Claude Code marketplace

Personal slash commands, skills and hooks for Claude Code, packaged as a plugin marketplace. The content comes from [michalkowol/ai](https://github.com/michalkowol/ai) (`common/commands`, `common/skills`, `config/claude/managed-settings.json`).

## Installation

```bash
/plugin marketplace add michalkowol/ai-tools   # or a local path to this checkout
/plugin install mk@michalkowol
/plugin install html-spec@michalkowol       # HTML specs, see below
/plugin install daily-workflow@michalkowol   # optional, see plugins/daily-workflow/README.md
```

Restart Claude Code (or run `/reload-plugins`) afterwards.

## Update

Push the changes first, the marketplace is fetched from GitHub (not needed when it was added from a local path). Then run:

```bash
/plugin marketplace update michalkowol
/plugin update mk@michalkowol
/plugin update html-spec@michalkowol
/plugin update daily-workflow@michalkowol
```

Restart Claude Code (or run `/reload-plugins`) afterwards. Bump `version` in the changed plugin's `.claude-plugin/plugin.json` with every change, otherwise `update` may not see it.

## Plugin `mk`

Plugin commands are namespaced, e.g. `/mk:commit`.

## Plugin `html-spec`

`/html-spec:init` sets up a project for planning in HTML files. It copies the `html-spec` and `html-spec-extract` skills into the project's `.claude/skills/`, so every engineer can use them without this plugin, and creates `.agents/docs/specs/` with `.agents/docs/INDEX.md`.

The init also copies the global `style.css` and `global-components.js` to `.agents/docs/specs/assets/`, so specs open from the repo without a server or internet access. Re-running the init upgrades the skills and the assets and migrates existing specs to the current spec format (see `plugins/html-spec/skills/init/MIGRATIONS.md`).

## Plugin `daily-workflow`

Work Logger hooks that record work from parallel Claude Code sessions into a local Worklog (`~/.ai/worklog`), plus `/daily-workflow:briefing` and `/daily-workflow:worklog`. Setup and usage: [plugins/daily-workflow/README.md](plugins/daily-workflow/README.md).

## License

MIT
