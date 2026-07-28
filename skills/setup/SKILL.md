---
name: setup
description: Use once per repository, or when its tracker or domain layout changes, to configure Project Truss as the user-facing facade for Matt-backed engineering methods.
---

# Project Truss Setup

Apply `docs/project-truss/contract.yml`. This is the only setup skill the user needs to invoke. It adopts Matt's repository-setup contract because `setup-matt-pocock-skills` is command-only; report that method as `facaded`, never invoked.

## Inspect before writing

Read live repository evidence:

- Git root, remotes, and the GitHub `OWNER/REPO`;
- existing `CLAUDE.md`, `AGENTS.md`, and their `## Agent skills` section;
- `docs/agents/`, root context files, ADR directories, and monorepo signals;
- the available Matt skill list, including whether triage is installed.

Project Truss is GitHub-native. Missing GitHub identity or authenticated `gh` capability is `github_capability_missing`. Prefer an existing `CLAUDE.md`; otherwise use an existing `AGENTS.md`. If neither exists, ask through `advanced-user-input` which one to create. Default to single-context domain docs unless genuine monorepo evidence requires one domain-layout decision.

## Confirm and apply

Show one concise draft covering the instruction block, tracker, domain layout, optional triage labels, and detected method capabilities. Resolve only a material choice before writing.

Resolve the installed Project Truss plugin root from this skill's location and store its absolute path in `PROJECT_TRUSS_ROOT`. Then run:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Setup -RepoRoot . -SetupJson \
  '{"repository":"OWNER/REPO","instruction_file":"AGENTS.md","domain_layout":"single-context","triage_enabled":true,"available_methods":["grilling","tdd","diagnosing-bugs","research","domain-modeling","prototype","resolving-merge-conflicts","code-review"]}'
```

The Setup action verifies that `RepoRoot`, its GitHub remote, and authenticated `gh` all match the selected repository. It verifies existing instruction preference and strong multi-context signals, records the inspected evidence, and idempotently owns bounded sections in one `## Agent skills` block plus `docs/agents/issue-tracker.md`, `domain.md`, and optional `triage-labels.md`. Preserve unrelated instructions and re-read every output. If unmarked existing guidance conflicts with the draft, resolve that material choice before applying; the action preserves it outside the managed section.

## Method truth

- `invocable`: an installed Matt method Truss may use when evidence triggers it.
- `facaded`: a command-only Matt contract implemented through Truss (`setup-matt-pocock-skills`, `wayfinder`).
- `missing`: a triggered required method that is unavailable; stop as `method_capability_missing`.
- `not_triggered`: available or known but irrelevant to the current work; do not load it.

Wayfinder decision maps clarify foggy destinations before Shape. They never become Truss execution contracts or lifecycle evidence. Users invoke `project-truss:setup` once and `project-truss:start` thereafter.
