---
name: shape
description: Use when a governed outcome needs the smallest executable native GitHub issue, dependency, parent, or milestone structure.
---

# Project Truss Shape

Apply `docs/project-truss/contract.yml`. Load a relevant card from `docs/project-truss/METHODS.md` only when its Trigger matches current evidence.

## Choose the smallest shape

Run `scripts/project-truss.sh -Action Plan` and show the dry result before any GitHub write.

- one mergeable unit: one leaf issue plus its pull request;
- several independently mergeable units: one parent with leaf sub-issues and only necessary dependencies;
- coordinated release, deadline, or cross-issue health target: add one milestone.

Every executable leaf uses the six contract headings exactly. Add repository-profile-specific assumptions, invariants, tolerances, or domain ownership only when relevant.

Do not create lifecycle labels, GitHub Projects, wrapper issues, title hierarchy markers, local issue files, or another durable tracker.

## Write with authority

Use explicit scope that already authorizes issue creation or ask once through `advanced-user-input`. Create issues with `gh issue create`. Connect native relationships with the current GitHub API:

```bash
gh api --method POST "repos/$repo/issues/$parent/sub_issues" --header "X-GitHub-Api-Version: 2026-03-10" -F sub_issue_id="$child_id"
gh api --method POST "repos/$repo/issues/$blocked/dependencies/blocked_by" --header "X-GitHub-Api-Version: 2026-03-10" -F issue_id="$blocker_id"
```

Create a milestone only for the full release shape. After every mutation, re-read the authoritative issue, sub-issue, dependency, and milestone state; report exact URLs. Stop on missing relationship support rather than inventing a compatibility layer.
