# Athena CLI Reference

Live sources when anything looks stale: `athena --help`, `athena <command> --help`,
and the documentation bundled with the Athena source.

### Global Flags

```
athena [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
athena chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
athena setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
athena model                Interactive model/provider picker
athena fallback [add|remove|list]  Fallback provider chain
athena config [show|edit|get|set|unset|path|env-path|check|migrate]
athena login / logout       OAuth sign-in / clear stored auth
athena doctor [--fix]       Check dependencies and config
athena status [--all]       Component status
```

### Tools & Skills

```
athena tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

athena skills list|browse|search QUERY|inspect ID
athena skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
athena skills config        Enable/disable skills per platform
athena skills check|update|uninstall|publish PATH
athena skills tap add REPO  Add a GitHub repo as a skill source
athena bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
athena mcp add NAME (--url or --command) | remove | list | test NAME
athena mcp catalog | install NAME     Curated catalog install
athena mcp configure NAME             Toggle tool selection
athena mcp serve                      Run Athena as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
athena gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `athena photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: use the messaging guide bundled with the Athena source.

### Sessions

```
athena sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
athena cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
athena webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
athena profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
athena profile rename A B | alias NAME | export NAME | import FILE
```

### Credentials & Pools

```
athena auth                 Interactive credential manager
athena auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
athena auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
athena desktop / gui        Native desktop app
athena dashboard            Web admin panel + embedded chat (--stop / --status)
athena proxy                OpenAI-compatible local proxy backed by an OAuth provider
athena portal               Quick setup / sign in via Nous Portal
athena kanban <verb>        Multi-agent work-queue board
athena project              Named multi-folder workspaces
athena skin list|use|set    Switch/tweak skins (see references/themes.md)
athena pets <verb>          Pet mascots (see references/petdex.md)
athena memory setup|status|off|reset   Memory provider
athena secrets bitwarden|onepassword   External secret stores
athena moa                  Mixture-of-Agents slots
athena hooks / security / backup / import / checkpoints / console
athena logs [-f] [errors]   View agent/error logs
athena send                 One-off message through a gateway platform
athena pairing / plugins / insights / journey / computer-use
athena acp                  ACP server (IDE integration)
athena completion bash|zsh|fish
athena update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `athena photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `athena config edit` · bundled configuration guide |
| Tools / toolsets | `athena tools list` · bundled tools reference |
| Skills catalog | `athena skills browse` · bundled skills catalog |
| Provider setup | `athena model` · bundled providers guide |
| Env variables | `athena config env-path` · bundled environment reference |
| Gateway logs | `~/.athena/logs/gateway.log` (or `athena logs`) |
| Sessions | `athena sessions browse` (reads state.db) |
