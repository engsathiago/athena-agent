# Langfuse Observability Plugin

This plugin ships bundled with Athena but is **opt-in** — it only loads when
you explicitly enable it.

## Enable

Pick one:

```bash
# Interactive: walks you through credentials + SDK install + enable
athena tools  # → Langfuse Observability

# Manual
pip install langfuse
athena plugins enable observability/langfuse
```

## Required credentials

Set these in `~/.athena/.env` (or via `athena tools`):

```bash
ATHENA_LANGFUSE_PUBLIC_KEY=pk-lf-...
ATHENA_LANGFUSE_SECRET_KEY=sk-lf-...
ATHENA_LANGFUSE_BASE_URL=https://cloud.langfuse.com   # or your self-hosted URL
```

Without the SDK or credentials the hooks no-op silently — the plugin fails
open.

## Verify

```bash
athena plugins list                 # observability/langfuse should show "enabled"
athena chat -q "hello"              # then check Langfuse for a "Athena turn" trace
```

## Optional tuning

```bash
ATHENA_LANGFUSE_ENV=production       # environment tag
ATHENA_LANGFUSE_RELEASE=v1.0.0       # release tag
ATHENA_LANGFUSE_SAMPLE_RATE=0.5      # sample 50% of traces
ATHENA_LANGFUSE_MAX_CHARS=12000      # max chars per field (default: 12000)
ATHENA_LANGFUSE_DEBUG=true           # verbose plugin logging
```

## Disable

```bash
athena plugins disable observability/langfuse
```
