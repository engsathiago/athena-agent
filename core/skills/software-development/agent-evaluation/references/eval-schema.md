# Evaluation Schema

## Manifest

```yaml
suite:
decision:
baseline:
candidate:
repository_revision:
agent_version:
model:
provider:
system_prompt_hash:
toolset_hash:
reasoning_setting:
memory_fixture:
sandbox:
timeout_seconds:
retry_policy:
repetitions:
token_budget:
cost_source:
run_date:
```

## Case

```yaml
id:
category:
input:
fixture:
hard_gates: []
deterministic_checks: []
rubric_dimensions: []
max_time_seconds:
max_cost:
```

## Scoring Order

1. Mark infrastructure-invalid runs separately; do not pretend they are model
   failures.
2. Apply hard gates. Any failed hard gate makes the case non-shippable.
3. Calculate deterministic task score.
4. Apply rubric/judge score only to qualities that cannot be executed.
5. Report efficiency beside quality; never blend them into an unexplained
   single number.
6. Aggregate median and range across repetitions. Show per-case regressions
   even when the average improves.

## Suggested Quality Dimensions

- deliverable completeness;
- factual/API correctness;
- runtime behavior;
- recovery and error handling;
- persistence after restart;
- tool choice and unnecessary calls;
- instruction adherence;
- security and secret hygiene;
- maintainability;
- evidence and citation integrity.
