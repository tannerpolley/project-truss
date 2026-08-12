---
name: setup
description: Use once per repository, or when its profile or guidance changes, to configure profile-aware Project Truss and available Matt techniques, then return to Start.
---

# Project Truss Setup

Apply `docs/project-truss/contract.yml`. Setup selects the repository profile and installs bounded guidance; it does not create lifecycle state or a prescribed scientific directory tree. Preview first, apply the confirmed profile, then return to `project-truss:start`.

## Discover

Read live Git/GitHub identity, `AGENTS.md` or `CLAUDE.md`, `CONTEXT.md` or `CONTEXT-MAP.md`, ADRs, `docs/agents/`, and the installed Matt skills. Select `application-development`, `scientific-computing`, or `general` from an existing exact `Repository Profile:` marker; ask one bounded question through `advanced-user-input` only when the intended profile cannot be established.

For scientific repositories, inspect existing benchmark, validation, research/lab, canonical-data, publication-lock, and validation-command paths as candidate defaults. Do not create absent paths or treat name-based discovery as scientific authority; the reviewed `scientific` Setup object is the repository-owned configuration and supports arbitrary paths and policies.

## Preview and apply

Resolve this plugin root as `PROJECT_TRUSS_ROOT`. Omitting `SetupJson` auto-discovers a read-only draft:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Setup -RepoRoot .
```

For an explicit draft, include `repository_profile`:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Setup -RepoRoot . -SetupJson \
  '{"repository":"OWNER/REPO","repository_profile":"scientific-computing","instruction_file":"AGENTS.md","domain_layout":"single-context","triage_enabled":true,"available_methods":["grilling","tdd","diagnosing-bugs","research","domain-modeling","prototype","resolving-merge-conflicts","code-review","codebase-design","cutthroat-code-cleanup","minimize-code-surface","wizard","writing-for-agents"]}'
```

Review the draft, including the complete `scientific` configuration object when present, then add `-Apply true`. Edit that object when repository-specific tolerance, compatibility, publication-lock, experimental-artifact, or path policy differs from discovery. Setup verifies the attached Git root and authenticated `gh` repository, preserves unrelated instructions, and owns bounded sections in the selected instruction file plus `docs/agents/issue-tracker.md`, `domain.md`, optional `triage-labels.md`, and profile-specific `scientific-computing.md`.

`invocable` means a triggered Matt technique can run; `missing` blocks governed work; `not_triggered` means irrelevant. Setup never invents method availability. Return to Start and continue the requested outcome.
