---
name: creative-campaign
description: Use when building a coherent multi-asset creative campaign.
license: MIT
metadata:
  athena:
    tags: [creative, campaign, image, video, audio, brand, social-media]
    category: creative
    related_skills: [claude-design, design-md, comfyui, youtube-content]
---

# Creative Campaign

## Overview

Treat a campaign as a reusable graph, not a bag of prompts. Separate creative
direction from provider syntax so the same plan can run through local models,
APIs, MCP tools, or manual production.

## Procedure

1. **Normalize the brief.** Capture objective, audience, offer, channels,
   deliverables, brand constraints, mandatory copy, references, formats,
   deadline, and acceptance criteria. Mark unknowns; do not invent logos,
   claims, prices, or legal text.

2. **Create the campaign spine.** Define one message, one visual thesis, a
   palette/type direction, recurring subjects, and continuity rules. Completion
   criterion: every planned asset can be traced to this spine.

3. **Build a dependency graph.** Generate foundations before derivatives:
   brand kit and hero concept -> key visual -> channel variants -> animation ->
   audio/lip-sync -> exports. Branch alternative concepts early; converge
   before expensive rendering.

4. **Route by capability.** Select a model/tool per node using required
   modality, edit precision, text rendering, reference support, aspect ratio,
   duration, local hardware, privacy, cost, and latency. Record the reason;
   provider popularity alone is not a reason.

5. **Compile prompts.** Use the provider-neutral blueprint in
   [references/prompt-blueprints.md](references/prompt-blueprints.md), then add
   only syntax the chosen backend actually supports. Keep speech, ambience,
   negative constraints, and on-screen copy in separate fields where possible.

6. **Generate cheap proofs.** Test composition, copy hierarchy, continuity,
   and motion with low-cost previews. Lock seeds/references and approved nodes.
   Do not upscale or render long video before the proof passes.

7. **Refine selectively.** Patch the failed node: edit, inpaint, restyle,
   relight, regenerate one shot, or replace one model. Avoid restarting the
   whole campaign when downstream dependencies remain valid.

8. **Assemble and validate.** Check brand consistency, legibility, safe zones,
   factual copy, platform dimensions, audio sync, clipping, duration, and
   export quality. Compare all variants side by side.

9. **Package the workflow.** Deliver final assets plus a manifest containing
   inputs, provider/model, parameters, seed, dependencies, cost, rights notes,
   and reproduction instructions. Remove credentials and private source files.

## Social and Marketing Layer

For each channel, define hook, value, proof, action, format, and success metric.
Generate multiple hook/visual combinations, not cosmetic copies of one idea.
Do not promise universal engagement benchmarks. Prefer measurements from the
user's account and label assumptions.

For Instagram collection or analysis, use official APIs when available. If
using Instaloader or similar tooling, operate only on content the user is
authorized to access and account for platform changes and rate limits.

## Local-First Routing

On limited hardware, prefer quantized/offloaded workflows, staged resolution,
short preview duration, and queueable jobs. Treat large synchronized
audio-video models as optional backends; they should not become a mandatory
Athena dependency.

## Common Pitfalls

1. Embedding a vendor name where a capability requirement belongs.
2. Creating 20 assets before approving the campaign spine.
3. Asking one model to perform typography, photorealism, layout, animation, and
   lip-sync in one opaque step.
4. Losing character/product consistency between nodes.
5. Copying prompt libraries verbatim instead of parameterizing intent.
6. Upscaling defects that should have been fixed at the composition stage.
7. Omitting model terms, source rights, or usage cost from the manifest.

## Verification Checklist

- [ ] Brief has objective, audience, formats, constraints, and acceptance tests.
- [ ] Asset graph records dependencies and approved nodes.
- [ ] Every model/tool choice has a capability-based reason.
- [ ] Mandatory text is verified separately from generated imagery.
- [ ] Brand, subject, product, and temporal continuity pass.
- [ ] Platform dimensions, safe zones, and audio/video sync pass.
- [ ] Final manifest can reproduce each delivered asset.
- [ ] Credentials and unauthorized source material are absent.

Read [references/prompt-blueprints.md](references/prompt-blueprints.md) before
compiling image, video, or campaign prompts.
