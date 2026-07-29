---
name: start
description: Use when Project Truss is explicit or a coding outcome needs merge, publication, multiple deliverables, delegation, a milestone, or continuity beyond one safe context.
---

# Project Truss Start

Own one outcome from classification through verified closeout. Users invoke only `project-truss:setup` and `project-truss:start`; Start routes all other Truss stages and engineering methods. Apply `docs/project-truss/contract.yml` and `docs/project-truss/METHODS.md`.

## Classify and preflight

Resolve the installed plugin root from this skill's location as `PROJECT_TRUSS_ROOT`. Run `"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Plan` with a faithful request. Include the repository profile and whether this is code or stable behavior; Plan infers canonical methods. Follow `next_action` and `method_routes`; never ask the user to select an internal skill. Direct work stays direct.

For an existing pull request, pass `-Repository OWNER/REPO -PullRequest N` to Plan. Plan reads live linked issues and treats their canonical resolution receipt as the claim record. With no matching receipt, review, verify, merge with authority, and safely clean the PR through ordinary Git/GitHub guidance; do not Shape a synthetic leaf or invoke Resolve/Close. A matching receipt remains governed, and unavailable or malformed evidence blocks.

Before governed work, verify `docs/agents/` setup and the actual available skill list. Pass `matt_configured` and `available_methods`; use `required_methods` only for additional task-specific methods. If setup is absent, route to `setup`. Missing any inferred or explicit method is `method_capability_missing`; never silently skip it.

## Grill before Shape

New governed outcomes and material rescope set `new_outcome` or `material_rescope` and perform Matt's current `grill-with-docs` contract: invoke `grilling` and actively apply `domain-modeling`. Ask decision questions one at a time with a recommendation, looking up facts instead of asking. Ask at least one question and do not act until the user explicitly confirms shared understanding. Capture resolved glossary terms or qualifying ADRs inline; create neither when no domain decision crystallizes.

Only then pass the actual question/answer decisions in `grilling_decisions` and the user's words in `shared_understanding_confirmation`. Resume an unchanged published issue without repeating the interview.

Method routes are explicit:

- `invocable`: invoke the installed Matt skill.
- `facaded`: Project Truss adopts a command-only Matt contract and produces its result.
- `missing`: stop with `method_capability_missing`.
- `not_triggered`: do not run the method.

When a material decision exceeds one safe context, Start performs the facaded Wayfinder contract before Shape. Name and grill the destination, create one `wayfinder:map` issue and native child decision tickets using the configured Wayfinding operations, then resolve at most one non-research frontier ticket per session. Once no decision fog remains, route to Shape. Treat the map and `## Question` tickets only as source context, never Truss execution issues or lifecycle evidence.

## Continuation loop

After every Shape, Resolve, Close, failure-recovery, merge, and Cleanup action, return to Start and re-read GitHub, Git, CI, reviews, and current worktrees. Use Status to choose the next stage from fresh truth. An implementation request authorizes routine in-scope issue, branch, pull-request, guarded merge, and exact outcome cleanup operations; ask only for a genuinely missing material decision or authority boundary.

Do not finish at issue publication, implementation, PR creation, CI completion, review, merge, or pre-cleanup. On verification, CI, or review failure, rerun Plan with the matching `failed_gate`, invoke its required `diagnosing-bugs`, repair the cause, and retry. Stop only on a blocker named in the contract, an intentional Wayfinder handoff, direct-work completion, or verified governed closeout.

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
- Use `close` when a governed selected set has a pull request or appears complete.

Ask through `advanced-user-input` only for a material decision or authority boundary. Otherwise re-enter from GitHub, Git, CI, canonical evidence, and current worktrees rather than remembered state.
