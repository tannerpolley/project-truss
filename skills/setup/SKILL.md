---
name: setup
description: Use once per repository, or when tracker/domain docs change, to preview or apply GitHub, Git, and Matt-compatible repository guidance, then return to Start.
---

# Project Truss Setup

Apply `docs/project-truss/contract.yml`. Setup is a callable Truss stage: inspect and preview safe defaults, apply only after the material choice is confirmed, then return to `project-truss:start`. Do not stop at setup when the user asked for engineering work.

## Inspect before writing

Read live repository evidence:

- Git root, remotes, and the GitHub `OWNER/REPO`;
- existing `CLAUDE.md`, `AGENTS.md`, and their `## Agent skills` section;
- `docs/agents/`, root context files, ADR directories, and monorepo signals;
- the available Matt skill list, including whether triage is installed.

Project Truss is GitHub-native. Missing GitHub identity or authenticated `gh` capability is `github_capability_missing`. Prefer an existing `CLAUDE.md`; otherwise use an existing `AGENTS.md`. If neither exists, ask through `advanced-user-input` which one to create. Default to single-context domain docs unless genuine monorepo evidence requires one domain-layout decision.

## Confirm and apply

The command is read-only by default and auto-detects repository, instruction file, domain layout, and existing triage guidance when `SetupJson` is omitted. Review its concise draft; use `-Apply true` only after any material choice is settled.

Resolve the installed Project Truss plugin root from this skill's location and store its absolute path in `PROJECT_TRUSS_ROOT`. Then run (the first command previews; add `-Apply true` to write):

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Setup -RepoRoot . -SetupJson \
  '{"repository":"OWNER/REPO","instruction_file":"AGENTS.md","domain_layout":"single-context","triage_enabled":true,"available_methods":["grilling","tdd","diagnosing-bugs","research","domain-modeling","prototype","resolving-merge-conflicts","code-review","codebase-design","cutthroat-code-cleanup","minimize-code-surface","scientific-coding-and-testing","wizard","writing-for-agents"]}'
```

The Setup action verifies that `RepoRoot`, its GitHub remote, and authenticated `gh` all match the selected repository. It verifies existing instruction preference and strong multi-context signals, records the inspected evidence, and idempotently owns bounded sections in one `## Agent skills` block plus `docs/agents/issue-tracker.md`, `domain.md`, and optional `triage-labels.md`. Preserve unrelated instructions and re-read every output. If unmarked existing guidance conflicts with the draft, resolve that material choice before applying; the action preserves it outside the managed section. Method availability is reported honestly; setup does not invent it.

## Method truth

- `invocable`: an installed Matt method Truss may invoke directly when evidence triggers it.
- `missing`: a triggered governed method that is unavailable; stop as `method_capability_missing`.
- `not_triggered`: available or known but irrelevant to the current work; do not load it.

Setup is native Truss configuration, not a Matt method. Wayfinder decision maps are native Truss planning artifacts that clarify foggy destinations before Shape; they never become execution contracts or lifecycle evidence. Return to Start after setup, complete the context/vocabulary pass, and let Start choose the next stage.
