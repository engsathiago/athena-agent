# Athena Memory

Athena Memory is a local-first persistent memory provider for Athena. It adds a
searchable record store beside the built-in `MEMORY.md` and `USER.md` files.

## Properties

- SQLite, FTS5 and bounded fuzzy hybrid recall; no network dependency.
- Profile-scoped database under `ATHENA_HOME`.
- Provenance, trust origin, confidence and importance on every memory.
- Temporal ranking and usage tracking.
- Deduplication and explicit supersession.
- Feedback, correction and permanent deletion.
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
    min_score: 0.30
    temporal_half_life_days: 120
```

Recall exposes lexical, fuzzy, recency and combined scores. The `history`
action returns the create/reinforce/update/feedback/supersede/forget event
timeline for one memory or the store, without copying memory content into the
audit table.
