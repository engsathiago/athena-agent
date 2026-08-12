# Provider-Neutral Prompt Blueprints

Keep fields structured until the final provider adapter. Omit unsupported
fields instead of smuggling them into prose.

## Image

```yaml
subject:
action_or_pose:
environment:
composition:
camera_and_lens:
lighting:
materials_and_texture:
palette:
style_reference:
mandatory_text:
negative_constraints:
aspect_ratio:
continuity_refs:
```

Verify mandatory typography after generation. If exact text matters, prefer a
text-capable model or add type during deterministic composition.

## Audio-Video Shot

```yaml
duration_seconds:
opening_frame:
subjects:
ordered_actions:
camera_motion:
scene_motion:
dialogue:
voice_direction:
ambience:
sound_effects:
music:
ending_frame:
continuity_refs:
negative_constraints:
```

Keep dialogue verbatim and identify speakers. Describe audible ambience and
effects independently from visible action. For multi-shot work, use one record
per shot and a continuity sheet across records.

## Campaign Node Manifest

```yaml
id:
purpose:
depends_on: []
inputs: []
capabilities_required: []
provider:
model:
parameters: {}
seed:
status: planned | proof | approved | rejected | final
cost:
output_paths: []
review_notes: []
rights_notes:
```

## Review Scorecard

Score 0-2 for each dimension: message clarity, brand fit, composition,
legibility, continuity, technical quality, channel fit, factual correctness,
and reproduction completeness. A zero blocks final delivery. Record the defect
at the node that introduced it.
