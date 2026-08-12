# Project Truss method routing

Project Truss owns profile selection, GitHub/Git continuity, scientific claim/evidence contracts, and continuation. Matt Pocock skills supply focused techniques. Users call Truss; Start invokes a Matt skill only when current evidence triggers it.

| Route | Meaning |
|---|---|
| `invocable` | Triggered and installed; invoke it now. |
| `missing` | Triggered but unavailable; block governed work truthfully. |
| `not_triggered` | Irrelevant to current evidence; do not load it. |

## Matt techniques

| Trigger | Matt skill | Truss use |
|---|---|---|
| Material ambiguity in scope or a scientific claim | `grilling` | One decision question at a time |
| Shared language, invariants, or formulation concepts are unclear | `domain-modeling` | Update `CONTEXT.md` or a qualifying ADR |
| A primary source or niche claim is uncertain | `research` | Establish source authority and a reusable note when useful |
| An executable design or numerical question needs cheap evidence | `prototype` | Throwaway experiment and recorded verdict |
| A demonstrated defect or numerical failure lacks a cause | `diagnosing-bugs` | Reproduction and causal repair |
| A durable discrete software contract has an approved public seam | `tdd` | Behavior-level regression contract |
| A deep module boundary is being designed | `codebase-design` | Small public surface around hidden complexity |
| Git has active merge/rebase conflicts | `resolving-merge-conflicts` | Verified resolution |
| Published code is ready for review | `code-review` | Standards over the diff; Spec per issue |
| Structural/high-risk code is complete | `minimize-code-surface`, `cutthroat-code-cleanup` | One minimal canonical implementation |
| A human-only procedure is required | `wizard` | A staged human-run script |
| Agent-facing instructions change | `writing-for-agents` | Progressive, explicit, single-sourced guidance |

## Scientific distinction

The scientific protocol is native Truss behavior, not an optional external method. Research establishes source authority; domain modeling sharpens formulation language; prototypes answer uncertain numerical design questions; code review judges implementation quality. None substitutes for the evidence packet or Science review.

TDD is not the default for scientific uncertainty. It runs only when the change includes a durable discrete software contract. Numerical claims instead require independent or explicitly locked oracles, justified tolerances, certificates, provenance, and result classification.

Missing a governed Matt technique is `method_capability_missing`. Light work reports a degradation and continues where safe. Setup never pretends that a user-invoked wrapper ran.
