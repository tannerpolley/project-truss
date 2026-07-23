---
name: shape
description: Use when a governed outcome needs the smallest executable native GitHub issue, dependency, parent, milestone, label, or optional Project membership structure.
---

# Project Truss Shape

Apply `docs/project-truss/contract.yml`. New outcomes and material rescope require grilling before publication. Once shared understanding exists, publish directly to GitHub; do not create a local planning gate or lifecycle mirror.

## Publish Matt contracts

Run `scripts/project-truss.sh -Action Plan` with verified Matt capabilities before writing.

- A root spec uses `Problem Statement`, `Solution`, `User Stories`, `Implementation Decisions`, `Testing Decisions`, `Out of Scope`, and `Further Notes`.
- A leaf ticket uses `Parent`, `What to build`, `Acceptance criteria`, and `Blocked by`.
- One mergeable unit needs one leaf and its pull request.
- Independent units need one root with native sub-issues and only real blocked-by edges.
- Add a milestone only for a coordinated release, deadline, or cross-issue health target.

Use native `gh issue create --parent`, `--blocked-by`, and `gh issue edit` relationship flags when available. Re-read every issue, relationship, milestone, body, and label after mutation. GitHub becomes authoritative immediately after verified publication.

## Labels

Preserve existing labels. Add only caller-requested descriptive or taxonomy labels such as `bug`, `area:cli`, or `priority:high`. The Matt `ready-for-agent` role maps to `agent-shaped`, which is advisory only.

Never create or interpret `ready`, `claimed`, `in-review`, `blocked`, or `done` labels as lifecycle state. Readiness is derived from contracts, dependencies, claims, pull requests, CI, and provider truth.

## Optional GitHub Project projection

Only configure projection from an explicit owner and project number. Use native GitHub CLI commands; the `gh projects` extension is optional:

```bash
gh project view PROJECT --owner OWNER --format json
gh project item-list PROJECT --owner OWNER --format json --limit 1000
gh project item-add PROJECT --owner OWNER --url ISSUE_URL --format json
```

For each root or leaf URL, call `scripts/project-truss.sh -Action Project -ProjectionJson '{"owner":"OWNER","project":PROJECT,"url":"URL","ensure":true}'`. It pre-reads membership, adds only a missing item, re-reads, and fails on truncated output. Record exactly one returned `GitHub Project projection: CANONICAL_URL` line under the root's `Further Notes`. Do not create Projects, change fields or Status, remove items, or use Project metadata in lifecycle derivation.

Missing native commands, access, OAuth scope, complete structured output, or verified membership produces `github_capability_missing` with safe remediation. Never run `gh auth refresh -h github.com -s project` without separate user approval.
