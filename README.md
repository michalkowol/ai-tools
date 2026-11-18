# Claude Code marketplace

Personal slash commands, skills and hooks for Claude Code, packaged as a plugin marketplace. The content comes from [michalkowol/ai](https://github.com/michalkowol/ai) (`common/commands`, `common/skills`, `config/claude/managed-settings.json`).

## Installation

```bash
/plugin marketplace add michalkowol/ai-tools   # or a local path to this checkout
/plugin install mk@michalkowol
```

Restart Claude Code (or run `/reload-plugins`) afterwards.

## Update

Push the changes first, the marketplace is fetched from GitHub (not needed when it was added from a local path). Then run:

```bash
/plugin marketplace update michalkowol
/plugin update mk@michalkowol
```

Restart Claude Code (or run `/reload-plugins`) afterwards. Bump `version` in `plugins/mk/.claude-plugin/plugin.json` with every change, otherwise `update` may not see it.

## Plugin `mk`

Plugin commands are namespaced, e.g. `/mk:commit`.

### HTML specs

`/mk:html-spec-init` sets up a project for planning in HTML files. It copies the `html-spec` and `html-spec-extract` skills into the project's `.claude/skills/`, so every engineer can use them without this plugin, and creates `.agents/docs/specs/` with `.agents/docs/INDEX.md`.

Specs load the global style and components from GitHub Pages:

- https://michalkowol.github.io/ai-tools/plugins/mk/skills/html-spec-init/assets/style.css
- https://michalkowol.github.io/ai-tools/plugins/mk/skills/html-spec-init/assets/components.js

The URLs are not versioned, so changes to these files must stay backwards compatible. They go live after merging to `main`.

## License

MIT
