---
name: start
description: Use to begin or resume profile-aware work; Start reads shared context, establishes the scientific or application claim, invokes relevant Matt techniques, and continues through truthful closeout or a named blocker.
---

# Project Truss Start

Apply `docs/project-truss/contract.yml` and `docs/project-truss/METHODS.md`. Own one outcome until direct completion or verified closeout. Do not make the user choose internal skills.

## Establish current truth

Resolve this plugin root as `PROJECT_TRUSS_ROOT`. Read the exact repository profile, configured `docs/agents/`, root `CONTEXT.md` or `CONTEXT-MAP.md`, nearest context, ADRs, Git/GitHub state, current worktrees, and installed Matt skills. Extract relevant canonical terms. Missing or conflicting shared vocabulary routes to `domain-modeling` and, when a decision is material, `grilling` through one question at a time.

Run Plan with `start_entry:true`, repository profile, context evidence, risk, scope completeness, change type, and actual method availability. Follow its `continuation`, `next_action`, and `method_routes`. Missing setup routes to `setup`; return here afterward.

## Apply the profile

Application-development work proceeds from user behavior and durable software contracts. Governed new outcomes or material rescope with incomplete decisions invoke Matt `grilling` and `domain-modeling`; complete light work skips the interview.

Scientific-computing work proceeds in this order:

1. scientific question;
2. falsifiable claim or claims;
3. sources, data, units, conventions, assumptions, and model version;
4. mathematical or numerical formulation;
5. numerical experiment or benchmark with a named oracle and tolerance basis;
6. implementation only when needed;
7. scientific review and evidence-backed GitHub closeout.

Pass `scientific_question`, `falsifiable_claims`, and `scientific_evidence_plan` to Plan. A missing question/claim or evidence plan is an instruction to continue the Start interview, not a reason to silently stop: invoke `research` for uncertain primary sources, `domain-modeling` for formulation language/invariants, `prototype` for an uncertain numerical design, and ask the smallest unresolved material question through `advanced-user-input`. Confirm what observation would falsify each claim before Shape. TDD is routed only when `durable_software_contract:true`; scientific uncertainty is not converted into generic red-green-refactor work.

## Choose the smallest lane

- `direct`: no durable Truss coordination.
- `light`: one standalone issue and pull request.
- `governed`: explicit governance, release/milestone work, multiple units, delegation, or unsafe context size.

Standalone issues do not need parents. Parent/leaf structure is optional and only for genuine decomposition. Labels, milestones, Projects, and optional status checks are advisory.

Before capturing an implementation base, run:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Prepare -RepoRoot .
```

Prepare discovers the canonical checkout, primary remote, and remote default branch, fetches with pruning, requires a clean checkout, and advances only by fast-forward. Dirty, ahead, diverged, detached, or ambiguous state is a truthful blocker; never reset, rebase, auto-stash, discard work, or assume `main`.

## Continue

Route to `shape` for missing publication, `resolve` for a selected Ready issue/set, and `close` for implementation or PR evidence. A research-only scientific issue whose evidence is already durable and needs no repository mutation may be claimed by sole assignment and executed without Prepare, an implementation receipt, worktree, branch, or PR; route its path-backed evidence directly to Close. If evidence files must enter Git history, use the normal synchronized branch/PR path even when no production code changes. After issue publication, PR creation, review, merge, pre-cleanup, failure recovery, and every stage result, consume the continuation token, re-read authoritative state, and keep going. Optional provider checks are context, not gates.

For an existing PR, Plan with `-Repository OWNER/REPO -PullRequest N`. Without a matching Truss receipt, review/merge/cleanup it directly; do not synthesize an issue. Stop only for a named contract blocker, missing material authority, direct completion, or verified closeout.
