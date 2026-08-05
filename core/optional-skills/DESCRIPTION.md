# Optional Skills

Skills opcionais incluídas na distribuição Athena que **não são ativadas por padrão**.

These skills ship with the athena-agent repository but are not copied to
`~/.athena/skills/` during setup. They are discoverable via the Skills Hub:

```bash
athena skills browse               # browse all skills, official shown first
athena skills browse --source official  # browse only official optional skills
athena skills search <query>       # finds optional skills labeled "official"
athena skills install <identifier> # copies to ~/.athena/skills/ and activates
```

## Why optional?

Some skills are useful but not broadly needed by every user:

- **Niche integrations** — specific paid services, specialized tools
- **Experimental features** — promising but not yet proven
- **Heavyweight dependencies** — require significant setup (API keys, installs)

By keeping them optional, we keep the default skill set lean while still
providing curated, tested, official skills for users who want them.
