# Third-party notices

Athena contains substantial modified portions of **Hermes Agent**, originally
published by Nous Research under the MIT License.

- Original copyright: Copyright (c) 2025 Nous Research
- Original license: MIT
- Upstream project: https://github.com/NousResearch/hermes-agent

The upstream copyright and permission notice are preserved in `LICENSE` and in
the vendored core's `LICENSE`. Athena is an independent derivative project;
the upstream project and its authors do not endorse this fork.

Architectural ideas informed by OpenClaw were reimplemented against Athena's
own runtime contracts. No claim of affiliation or endorsement is made.

## Additional research references

Athena's progressive-memory and bundled workflow skills were independently
implemented after studying the following permissively licensed projects:

- `thedotmack/claude-mem` — Apache-2.0
- `headroomlabs-ai/headroom` — Apache-2.0
- `henrydaum/second-brain` — MIT
- `jordan-gibbs/hyperresearch` — MIT
- `paperclipai/paperclip` — MIT
- `msitarzewski/agency-agents` — MIT
- `mattpocock/sandcastle` and `mattpocock/evalite` — MIT
- `diegosouzapw/OmniRoute` — MIT
- `vercel-labs/skills` — MIT
- `Anil-matcha/Open-AI-Design-Agent` and `Open-Generative-AI` — MIT
- `engsathiago/EVE_Autonomo` — MIT (workflow ideas independently reimplemented)

`engsathiago/EVE-Agent` was also reviewed as a research reference. Its
repository did not include a root license file at the revision reviewed, so no
source code or protected assets from it were copied into Athena.

No affiliation or endorsement is implied. The detailed review and the rules
used for sources with missing or restrictive licenses are documented in
`docs/ANALISE_E_REFERENCIAS_ATHENA_2026.md`.
