# Claude Code marketplace

Personal slash commands, skills and hooks for Claude Code, packaged as a plugin marketplace. The content comes from [michalkowol/ai](https://github.com/michalkowol/ai) (`common/commands`, `common/skills`, `config/claude/managed-settings.json`).

## Installation

```bash
/plugin marketplace add michalkowol/ai-tools   # or a local path to this checkout
/plugin install mk@michalkowol
```

Restart Claude Code (or run `/reload-plugins`) afterwards.

## Plugin `mk`

Plugin commands are namespaced, e.g. `/mk:commit`.

## License

MIT
