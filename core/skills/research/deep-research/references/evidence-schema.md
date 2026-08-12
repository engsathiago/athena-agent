# Evidence Ledger Schema

Use one record per claim-source relationship. A claim supported by three
sources has three records; this makes independence and disagreement visible.

| Field | Meaning |
|---|---|
| claim_id | Stable local identifier such as `C-014` |
| claim | One falsifiable sentence |
| source_id | Identifier from the citation ledger |
| source_class | primary, official docs, paper, dataset, independent analysis, testimony |
| stance | supports, contradicts, contextualizes |
| evidence | Short paraphrase or verified quote pointer |
| published_at | Source publication/update date |
| observed_at | Retrieval date |
| scope | Population, version, geography, time range, or benchmark setup |
| confidence | high, medium, low, with a reason |
| status | verified, disputed, superseded, unresolved |

## Merge Rules

1. Deduplicate by underlying evidence, not URL. Syndicated articles are one
   evidence line.
2. Never replace a contradiction with the preferred interpretation. Keep both
   records and explain the weighting in `tensions.md`.
3. A newer source supersedes an older source only when it covers the same scope
   and explicitly replaces the earlier state.
4. Confidence belongs to a claim-source relationship, not to the source as a
   whole.
5. Preserve the original wording of the canonical question in every branch.

## Critic Finding Schema

```text
finding_id:
severity: blocking | material | minor
claim_id:
defect:
evidence_needed:
proposed_patch:
status: open | verified | rejected | patched
```

A proposed patch is not evidence. Verify it before changing the draft.
