# Athena heartbeat checklist

Keep this list short. A heartbeat should inspect durable signals and stay
silent unless something is new, relevant, and actionable.

- Review overdue commitments explicitly recorded in memory.
- Review failed or blocked scheduled work.
- Surface important changes since the previous successful heartbeat.
- Do not send routine “all good” messages; use `[SILENT]` when no action is needed.
