---
name: agent-evaluation
description: Use when evaluating agents, models, prompts, or tools.
license: MIT
metadata:
  athena:
    tags: [evals, benchmarks, agents, models, quality, regression]
    category: software-development
    related_skills: [test-driven-development, systematic-debugging, requesting-code-review]
---

# Agent Evaluation

## Overview

Evaluate the model plus harness, not the model name in isolation. The prompt,
tools, system instructions, provider adapter, sandbox, retries, memory state,
and validation environment are all experimental conditions.

## Procedure

1. **State the decision.** Define what the evaluation will choose or protect:
   model routing, prompt release, memory change, tool regression, or production
   readiness. A leaderboard without a decision is not a useful eval.

2. **Freeze conditions.** Record code revision, agent version, model/provider,
   system prompt hash, toolset, reasoning setting, context state, timeout,
   retries, sandbox, dependency versions, date, and pricing source.

3. **Design representative tasks.** Include routine, ambiguous, failure,
   recovery, long-context, and adversarial-but-in-scope cases. Keep a private
   holdout set when optimizing prompts.

4. **Define assertions before runs.** Prefer executable checks: process boots,
   API responds, expected file exists, citation resolves, state persists after
   restart, tool was or was not called, and secrets are absent. Do not reward
   file count, verbosity, or tests that merely mock the same invented API.

5. **Run isolated repetitions.** Start from the same fixture, use unique output
   directories, retain raw traces, and run enough repeats to expose variance.
   Do not let one run's memory contaminate the next unless memory is the feature
   under test.

6. **Validate reality.** Execute the produced artifact against real libraries
   and local services where safe. A green mocked test cannot prove that a
   generated API call exists.

7. **Score in layers.** Apply hard gates first, deterministic metrics second,
   and rubric or judge scoring last. A judge cannot override a failed boot,
   missing deliverable, leaked secret, or fabricated citation.

8. **Measure efficiency.** Capture input/output/cache/reasoning tokens, calls,
   wall time, retries, failures, and estimated cost. Compare quality at equal
   budgets and cost at equal quality.

9. **Analyze failures by class.** Distinguish model knowledge, harness context,
   tool schema, provider interoperability, orchestration, timeout, and test
   weakness. Reproduce the class before changing the system.

10. **Set a release gate.** Compare candidate against baseline and publish the
    raw conditions, confidence, regressions, and exceptions. Block only on
    predefined gates.

## Delegation Experiments

Test solo and delegated variants separately. Delegation is justified when work
is independent, specialists have distinct context/tools, or a cheap executor
preserves quality. Track coordination overhead. Forced delegation that adds
latency without improving a predefined metric is a regression.

## Memory Experiments

Evaluate retrieval precision, recall, stale-memory correction, provenance,
forget semantics, context tokens injected, and behavior after restart. Include
conflicting old/new facts and untrusted imported content. Verify that memory
failure degrades gracefully and does not block the core agent loop.

## Minimum Artifact Set

```text
evals/<suite>/
  manifest.yaml       # frozen conditions and budgets
  cases.yaml          # inputs, fixtures, hard assertions
  rubric.md           # only dimensions not executable as checks
  runs/<run-id>/      # trace, outputs, metrics, validation log
  report.md           # aggregate, failures, decision
```

Use [references/eval-schema.md](references/eval-schema.md) for fields and the
recommended scoring order.

## Common Pitfalls

1. Comparing models under different system prompts without labeling the
   harness effect.
2. Optimizing on the same cases used for final reporting.
3. Counting tests instead of checking whether they exercise real behavior.
4. Using one run for a stochastic system.
5. Hiding timeouts or malformed provider responses as zero scores.
6. Letting an LLM judge overrule deterministic failures.
7. Reporting price or model availability without a dated source.

## Verification Checklist

- [ ] The evaluation answers a concrete decision.
- [ ] Harness and provider conditions are frozen and reported.
- [ ] Assertions were written before observing candidate outputs.
- [ ] Real runtime validation covers critical integrations.
- [ ] Repetitions and variance are reported.
- [ ] Quality, cost, latency, and failure rate are separate metrics.
- [ ] Raw traces and validation logs are retained with secrets redacted.
- [ ] Release decision follows predefined gates.
