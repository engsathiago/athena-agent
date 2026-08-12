---
name: deep-research
description: Use when research needs evidence and contradiction checks.
license: MIT
metadata:
  athena:
    tags: [research, citations, evidence, synthesis, fact-checking]
    category: research
    related_skills: [grounded-citations, research-paper-writing, arxiv]
---

# Deep Research

## Overview

Turn an open-ended question into a reproducible research run. Preserve the
canonical question, evidence, disagreements, rejected leads, and citations so
another session can resume without restarting.

Use `grounded-citations` for the citation ledger. This skill owns the research
strategy around that ledger.

## Choose a Tier

| Tier | Use for | Breadth | Critique |
|---|---|---:|---:|
| light | bounded factual comparison | 3-6 strong sources | one contradiction pass |
| full | decisions, market/technical reports | 8-20 sources | two independent critiques |
| exhaustive | disputed or high-impact work | question-dependent; stop by saturation | specialist critiques + citation audit |

Escalate the tier when sources disagree, the answer changes a costly decision,
or the user asks for exhaustive coverage. Do not inflate source count with
duplicate reporting.

## Durable Run Layout

For a file-backed deliverable, create one run directory:

```text
research/<slug>/
  manifest.md       # canonical question, scope, tier, status, next step
  evidence.md       # claim -> source -> support/contradiction
  tensions.md       # unresolved disagreements and uncertainty
  draft.md          # current synthesis
  sources.json      # grounded-citations ledger
```

Update `manifest.md` after every phase. Completion criterion: a new session can
identify the exact next action by reading only the manifest.

## Procedure

1. **Canonicalize.** Write one primary question, decision context, inclusions,
   exclusions, freshness cutoff, and completion criteria. Do not silently
   broaden it later.

2. **Decompose.** Split into answerable subquestions: definitions, mechanism,
   alternatives, evidence for, evidence against, limitations, and current
   status. Mark dependencies between them.

3. **Search for breadth.** Find primary sources first, then independent
   corroboration. Register sources as they are found. Stop a branch when two
   consecutive searches add no new claim, source class, or contradiction.

4. **Build the evidence ledger.** Record each load-bearing claim with source,
   date, evidence type, confidence, and whether it supports or contradicts.
   Keep facts separate from interpretations.

5. **Search for depth.** Target weak claims, missing source classes, and every
   tension. Prefer a narrow query that could disprove the current hypothesis.

6. **Reconcile.** Explain disagreements by scope, date, methodology, incentives,
   or definitions. If reconciliation is impossible, preserve the disagreement
   instead of averaging it away.

7. **Draft from evidence.** Write the answer from the ledger, not from search
   snippets or memory. Cite while drafting. State uncertainty near the claim.

8. **Critique.** Run distinct passes for: missing evidence, alternative
   explanation, numerical/date errors, and user-question alignment. A critique
   must name a concrete defect or return `no finding`; generic caution is not a
   finding.

9. **Patch, do not restart.** Fix only verified defects in the current draft.
   Regenerating the whole report after critique can reintroduce already-fixed
   errors and citation drift.

10. **Verify.** Check citation identities, quoted evidence, links, date scope,
    unresolved tensions, and whether every conclusion answers the canonical
    question. Mark the manifest complete only after all gates pass.

## Delegation

Delegate only independent evidence branches or independent critiques. Give each
worker the canonical question, one bounded subquestion, source requirements,
and an output schema. Do not delegate the final synthesis unless one agent owns
the complete evidence ledger and verifies every merged claim.

## Output Contract

Lead with the answer. Then provide the decisive evidence, material uncertainty,
alternatives, and sources. Separate:

- verified findings;
- reasoned inference;
- unresolved questions;
- recommended next action, when the research supports one.

## Common Pitfalls

1. Treating many search results as many independent sources.
2. Citing a source that mentions the topic but does not support the claim.
3. Hiding disagreements inside a smooth summary.
4. Letting the research drift away from the canonical question.
5. Rewriting the full report after every critique.
6. Reporting benchmark or vendor claims without checking methodology.

## Verification Checklist

- [ ] Canonical question and scope are explicit.
- [ ] Every load-bearing external claim has a supporting source.
- [ ] Primary sources were preferred where available.
- [ ] Contradictions and negative evidence were actively searched.
- [ ] Inference and fact are visibly distinct.
- [ ] Critics produced concrete findings or `no finding`.
- [ ] Final patches did not break citation mapping.
- [ ] The answer satisfies the original completion criteria.

Read [references/evidence-schema.md](references/evidence-schema.md) when
creating a durable evidence ledger or merging parallel research branches.
