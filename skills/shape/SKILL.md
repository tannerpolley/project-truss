---
name: shape
description: Use after Start selects publication to create the smallest native GitHub issue shape—standalone by default, parent/leaf only for coordinated work—with optional dependencies, labels, milestones, or Project projection, then return to Start.
---

# Project Truss Shape

Apply `docs/project-truss/contract.yml`. Shape is the Truss publication stage after Start's risk/completeness check and any needed Matt grilling/domain modeling. Publish the smallest native GitHub structure, then return to Start; do not create a local planning gate or lifecycle mirror.

If Start supplies a completed native Wayfinder map, read it as decision context and link it under `Further Notes` when useful. Create a standalone execution issue for one self-contained outcome. Use a root with child leaves only for genuinely decomposed or coordinated work; never invent a parent for convenience. Never reuse Wayfinder questions as execution tickets or infer Truss state from their labels, assignees, comments, or closure.

## Publish Matt contracts

Run `"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Plan` with verified Matt capabilities before writing.

- A root spec uses `Problem Statement`, `Solution`, `User Stories`, `Implementation Decisions`, `Testing Decisions`, `Out of Scope`, and `Further Notes`.
- A standalone ticket uses `What to build`, `Acceptance criteria`, and `Blocked by`.
- A leaf adds `Parent` only when it belongs to a real root; one light mergeable unit uses one issue and pull request.
- Independent units need one root with native sub-issues and only real blocked-by edges.
- Add a milestone only for a coordinated release, deadline, or cross-issue health target.

Use native `gh issue create --parent`, `--blocked-by`, and `gh issue edit` relationship flags when available. Re-read every issue, relationship, milestone, body, and label after mutation. GitHub becomes authoritative immediately after verified publication.

## Labels

Preserve existing labels. Add only caller-requested descriptive or taxonomy labels such as `bug`, `area:cli`, or `priority:high`. The Matt `ready-for-agent` role maps to `agent-shaped`, which is advisory only.

Labels may be used as advisory routing or status hints, including lifecycle-shaped names, but never as lifecycle proof. Readiness is derived from contracts, dependencies, claims, pull requests, and provider truth; optional status checks do not determine it.

## Optional GitHub Project projection

Only configure projection from an explicit owner and project number. Use native GitHub CLI commands; the `gh projects` extension is optional:

```bash
gh project view PROJECT --owner OWNER --format json
gh project item-list PROJECT --owner OWNER --format json --limit 1000
gh project item-add PROJECT --owner OWNER --url ISSUE_URL --format json
```

For each issue or PR URL, call `"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Project -ProjectionJson '{"owner":"OWNER","project":PROJECT,"url":"URL","ensure":true,"required":false}'`. It pre-reads membership, adds only a missing item, and paginates bounded output. Projection is advisory by default; set `required:true` only when the user makes membership an acceptance requirement. Do not create Projects, change fields or Status, remove items, or use Project metadata in lifecycle derivation.

Missing native commands, access, OAuth scope, or complete structured output is an advisory finding unless `required:true`. Never run `gh auth refresh -h github.com -s project` without separate user approval.
