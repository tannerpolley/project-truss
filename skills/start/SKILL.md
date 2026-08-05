---
name: start
description: Use to begin or resume Matt-first work; Start performs the repository context and shared-vocabulary pass, selects direct, light, or governed coordination, invokes only relevant Matt disciplines, and continues until completion or a named blocker.
---

# Project Truss Start

Own one outcome from classification through completion. Start is the normal Matt-first entrypoint: choose the smallest lane, invoke callable Matt disciplines directly, re-read authoritative state, consume each continuation token, and keep going until direct completion, a real decision/authority blocker, or verified closeout. Apply `docs/project-truss/contract.yml` and `docs/project-truss/METHODS.md`.

## Classify and preflight

Resolve the installed plugin root from this skill's location as `PROJECT_TRUSS_ROOT`. Run `"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Plan` with a faithful request, including `start_entry: true`, profile, code/behavior seam, risk, scope completeness, and any `design_change`, `manual_procedure`, or `agent_document_change` trigger. Plan selects `direct`, `light`, or `governed`; follow its `continuation`, `next_action`, and `method_routes` without asking the user to choose an internal skill. Direct work stays direct; light work may show degraded optional methods without stopping.

For an existing pull request, pass `-Repository OWNER/REPO -PullRequest N` to Plan. Plan reads live linked issues and treats their canonical resolution receipt as the claim record. With no matching receipt, review, verify, merge with authority, and safely clean the PR through ordinary Git/GitHub guidance; do not Shape a synthetic leaf or invoke Resolve/Close. A matching receipt remains governed, and unavailable or malformed evidence blocks.

Before governed work, verify `docs/agents/` setup and the actual available Matt skill list. Pass `matt_configured` and `available_methods`; use `required_methods` only for additional task-specific methods. If setup is absent, route to `setup`; after Setup, return here. Missing a triggered governed method is `method_capability_missing`; light work reports the degradation and continues.

## Read context and vocabulary

On every new Start entry, read the discovered root `CONTEXT.md` or `CONTEXT-MAP.md` and the nearest applicable context file before shaping or implementation. Treat it as shared language: extract the relevant canonical terms into `context_terms`, pass `context_reviewed: true`, and never use it as a scratchpad, implementation spec, or lifecycle ledger. If the context file is missing, a term is absent, or language is fuzzy or conflicting, invoke Matt's model-invocable `domain-modeling` and `grilling` disciplines. Ask one concise question at a time through `project-truss:advanced-user-input` when the answer is material, update `CONTEXT.md` inline when a term is settled, and use an ADR only for a surprising, hard-to-reverse trade-off. Do not claim the context pass is complete by setting `scope_complete`.

Plan reports `context_required` or `vocabulary_required` when this pass is incomplete. Follow its continuation back into Start, then re-plan with the observed files, terms, and confirmation. Clear vocabulary lets low-risk light work continue without an interview; governed new outcomes or material rescope require `vocabulary_confirmed: true` before Shape. An unchanged existing PR resumes without repeating the pass.

## Grill only when needed

Only governed new outcomes or material rescope with incomplete decisions invoke Matt's `grilling` and `domain-modeling` skills directly. Ask one concise question at a time with a recommendation, look up facts instead of asking, and do not Shape until shared understanding is confirmed. Complete, low-risk light requests skip the interview.

Only then pass the actual question/answer decisions in `grilling_decisions` and the user's words in `shared_understanding_confirmation`. Resume an unchanged published issue without repeating the interview.

Matt method routes are explicit:

- `invocable`: invoke the installed Matt skill directly.
- `missing`: stop with `method_capability_missing`.
- `not_triggered`: do not run the method.

When the task contains a human-only provisioning, secret, dashboard, migration, or cutover procedure, invoke Matt's model-invocable `wizard` and produce the staged human-run script; do not run it end to end. When changing skills, `AGENTS.md`, `CLAUDE.md`, or other agent-facing contracts, invoke `writing-for-agents` and keep the instructions progressive, explicit, and single-sourced.

When a material decision exceeds one safe context, Start owns the native Wayfinder planning path before Shape. Name and grill the destination, create one `wayfinder:map` issue and native child decision tickets using the configured operations, then resolve at most one non-research frontier ticket per session. Once no decision fog remains, route to Shape. Treat the map and `## Question` tickets only as source context, never execution issues or lifecycle evidence.

## Continuation loop

After every Shape, Claim, Resolve, Close, failure-recovery, merge, and Cleanup action, consume the returned continuation token, re-read GitHub, Git, reviews, optional provider checks, and worktrees, then perform its named next action in the same turn. An implementation request authorizes routine in-scope issue, branch, pull-request, guarded merge, and exact outcome cleanup operations; ask only for a genuinely missing material decision or authority boundary.

Do not finish at issue publication, implementation, PR creation, review, merge, or pre-cleanup. On verification or review failure, rerun Plan with the matching `failed_gate`, invoke its required `diagnosing-bugs`, repair the cause, and retry. Optional provider checks do not add a lifecycle gate. Stop only on a blocker named in the contract, an intentional Wayfinder handoff, direct-work completion, or verified governed closeout.

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

Ask through `advanced-user-input` only for a material decision or authority boundary. Otherwise re-enter from GitHub, Git, canonical evidence, optional provider checks, and current worktrees rather than remembered state.
