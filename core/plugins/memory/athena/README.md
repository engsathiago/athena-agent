# Athena Memory

Athena Memory is a local-first persistent memory provider for Athena. It adds a
searchable record store beside the built-in `MEMORY.md` and `USER.md` files.

## Properties

- SQLite, FTS5 and bounded fuzzy hybrid recall; no network dependency.
- Profile-scoped database under `ATHENA_HOME`.
- Provenance, trust origin, confidence and importance on every memory.
- Temporal ranking and usage tracking.
- Progressive disclosure: compact search, chronological timeline and full get.
- Deduplication and explicit supersession.
- Feedback, correction and permanent deletion.
- Structured task reflection with Delivered/Quality/Next/Learned fields.
- Dry-run hygiene review for stale, weak and near-duplicate records.
- Safe soft-archival that never automatically archives owner/system memory.
- Content-free audit events survive hard forget without retaining forgotten text.
- Built-in memory writes are mirrored after the normal approval flow.
- Automatic transcript capture is disabled by default.

Enable it with:

```yaml
memory:
  provider: athena

plugins:
  athena-memory:
    db_path: "$ATHENA_HOME/memories/athena_memory.db"
    auto_capture: false
    recall_limit: 6
    prefetch_item_max_chars: 700
    prefetch_max_chars: 4000
    min_score: 0.30
    temporal_half_life_days: 120
    maintenance_stale_after_days: 180
    maintenance_low_confidence: 0.35
```

Use `search` to choose compact candidates, `timeline` to inspect the records
around one candidate, and `get` to expand only the IDs needed. `recall` remains
available for backward compatibility and returns full matches.

Use `reflect` after significant work when there is a reusable lesson. It
stores what was delivered, observed quality, the next action and the lesson as
a normal correctable `lesson` memory; routine turns should not create one.

Recall exposes lexical, fuzzy, recency and combined scores. The separate
`history` action returns create/reinforce/update/feedback/supersede/forget
audit events for one memory or the store, without copying memory content into
the audit table.

Use `review` for a read-only hygiene report. `maintain` is also a dry run by
default; pass `dry_run: false` to soft-archive only its safe candidates. The
records remain in SQLite for audit and recovery, and owner/system memories are
always protected from automatic maintenance.
