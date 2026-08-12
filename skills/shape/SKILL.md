---
name: shape
description: Use after Start confirms the profile-specific outcome to publish the smallest native GitHub issue shape, then return to Start.
---

# Project Truss Shape

Apply `docs/project-truss/contract.yml`. Publish the smallest executable GitHub contract from the confirmed context and Matt-assisted decisions. A self-contained outcome is standalone; use a root and leaves only for genuine decomposition. Never invent a parent.

## Profile contracts

Application roots use `Problem Statement`, `Solution`, numbered `User Stories`, `Implementation Decisions`, `Testing Decisions`, `Out of Scope`, and `Further Notes`. Standalone issues use `What to build`, checkbox `Acceptance criteria`, and `Blocked by`; leaves add `Parent`.

Scientific roots use `Scientific Question`, `Falsifiable Claims`, `Evidence and Sources`, `Mathematical or Numerical Formulation`, `Benchmark and Validation Plan`, checkbox `Acceptance and Falsification Criteria`, `Out of Scope`, and `Further Notes`. Scientific standalone issues use `Claim to Establish`, `Inputs and Sources`, `Experiment or Implementation`, checkbox `Acceptance and Falsification Criteria`, `Required Evidence`, and `Blocked by`; leaves add `Parent`.

Scientific criteria must permit a supported negative result. State the expected evidence packet, oracle independence, tolerance basis, provenance, and what `VERIFIED`, `FALSIFIED`, or an inconclusive classification would mean.

Use native `gh issue create --parent`, `--blocked-by`, and `gh issue edit` relationships when available. Add milestones only for real release/deadline/cross-issue coordination. Re-read every mutation.

## Advisory projections

Preserve labels. Add only requested descriptive labels; `ready-for-agent` maps to `agent-shaped`, which is advisory only. Labels never prove lifecycle state.

An explicit GitHub Project owner/number may use:

```bash
gh project view PROJECT --owner OWNER --format json
gh project item-list PROJECT --owner OWNER --format json --limit 1000
gh project item-add PROJECT --owner OWNER --url ISSUE_URL --format json
```

Verify membership through the Truss Project action. Membership is advisory unless the user explicitly makes it acceptance evidence. Never create Projects, mutate fields/Status, or derive lifecycle from them. Never run `gh auth refresh` without separate approval.

GitHub is authoritative after verified publication. Return to Start; issue publication is not terminal.
