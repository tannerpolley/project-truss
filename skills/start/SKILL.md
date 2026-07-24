---
name: start
description: Use when Project Truss is explicit or a coding outcome needs merge, publication, multiple deliverables, delegation, a milestone, or continuity beyond one safe context.
---

# Project Truss Start

Own one outcome from classification through verified closeout. Apply `docs/project-truss/contract.yml` and use `docs/project-truss/METHODS.md` to route engineering technique.

## Classify and preflight

Run `scripts/project-truss.sh -Action Plan` with a faithful request. Direct work stays direct and may use any relevant Matt Pocock engineering skill without creating Truss structure.

Before governed work, verify the repository's Matt setup in `docs/agents/`, the available skill list, and every method required by the current task. Pass `matt_configured`, `required_methods`, and `available_methods` in the request. Stop on `method_capability_missing`; do not pretend a command-only or unavailable skill ran.

New governed outcomes and material rescope set `new_outcome` or `material_rescope`. They require grilling to shared understanding, using domain modeling when terminology or invariants matter. Resume an unchanged issue from current truth without repeating the interview.

## Synchronize before resolution

Before any implementation-base receipt or feature worktree is created, enter the canonical checkout and run:

```bash
scripts/project-truss.sh -Action Prepare -RepoRoot .
```

Prepare discovers the canonical checkout, primary remote, and remote default branch from live Git state. It requires the canonical checkout to be clean, fetches the primary remote with pruning, and advances the local default branch only by fast-forward. Its returned full `implementation_base` is the only valid base for the new resolution branch/worktree.

Treat `state_contradiction` from a dirty, non-default, ahead, or diverged canonical checkout as a truthful blocker. Never reset, rebase, auto-stash, discard work, assume the branch is named `main`, or capture the base before Prepare succeeds.

## Route from current truth

- Use `shape` when the native GitHub structure is absent or materially wrong.
- Use `resolve` when one or more explicitly selected Ready leaves can proceed or a recorded resolution set must continue.
- Use `close` when a selected set has a pull request or appears complete.

Ask through `advanced-user-input` only for a material decision or authority boundary. Otherwise re-enter from GitHub, Git, CI, canonical evidence, and current worktrees rather than remembered state.
