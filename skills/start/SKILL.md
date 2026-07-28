---
name: start
description: Use when Project Truss is explicit or a coding outcome needs merge, publication, multiple deliverables, delegation, a milestone, or continuity beyond one safe context.
---

# Project Truss Start

Own one outcome from classification through verified closeout. Users invoke only `project-truss:setup` and `project-truss:start`; Start routes all other Truss stages and Matt engineering methods. Apply `docs/project-truss/contract.yml` and `docs/project-truss/METHODS.md`.

## Classify and preflight

Resolve the installed Project Truss plugin root from this skill's location and store its absolute path in `PROJECT_TRUSS_ROOT`. Run `"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Plan` with a faithful request. Follow its `next_skill` and `method_routes`; do not ask the user to select an internal skill. Direct work stays direct and may invoke any triggered Matt method without creating Truss structure.

Before governed work, verify the repository's Matt setup in `docs/agents/`, the available skill list, and every method required by the current task. Pass `matt_configured`, `required_methods`, and `available_methods` in the request. If setup is absent, route to `project-truss:setup`. Stop on `method_capability_missing`; do not pretend an unavailable method ran.

New governed outcomes and material rescope set `new_outcome` or `material_rescope`. They require grilling to shared understanding, using domain modeling when terminology or invariants matter. Resume an unchanged issue from current truth without repeating the interview.

Method routes are explicit:

- `invocable`: invoke the installed Matt skill.
- `facaded`: Project Truss adopts a command-only Matt contract and produces its result.
- `missing`: stop with `method_capability_missing`.
- `not_triggered`: do not run the method.

When a material decision exceeds one safe context, Start performs the facaded Wayfinder contract before Shape. Name and grill the destination, create one `wayfinder:map` issue and native child decision tickets using the configured Wayfinding operations, then resolve at most one non-research frontier ticket per session. Once no decision fog remains, route to Shape. Treat the map and `## Question` tickets only as source context, never Truss execution issues or lifecycle evidence.

## Synchronize before resolution

Before any implementation-base receipt or feature worktree is created, enter the canonical checkout and run:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Prepare -RepoRoot .
```

Prepare discovers the canonical checkout, primary remote, and remote default branch from live Git state. It requires the canonical checkout to be clean, fetches the primary remote with pruning, and advances the local default branch only by fast-forward. Its returned full `implementation_base` is the only valid base for the new resolution branch/worktree.

Treat `state_contradiction` from a dirty, non-default, ahead, or diverged canonical checkout as a truthful blocker. Never reset, rebase, auto-stash, discard work, assume the branch is named `main`, or capture the base before Prepare succeeds.

## Route from current truth

- Use `shape` when the native GitHub structure is absent or materially wrong.
- Use `resolve` when one or more explicitly selected Ready leaves can proceed or a recorded resolution set must continue.
- Use `close` when a selected set has a pull request or appears complete.

Ask through `advanced-user-input` only for a material decision or authority boundary. Otherwise re-enter from GitHub, Git, CI, canonical evidence, and current worktrees rather than remembered state.
