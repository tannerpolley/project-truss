# ADR 0003: Native scientific-computing profile

## Status

Accepted

## Context

Project Truss 2 treated scientific repositories as application-development work with an additional scientific coding skill. That still began from implementation seams and stable behavior, encouraged generic TDD as the default, and lacked a durable distinction between source authority, mathematical formulation, numerical verification, empirical validation, and reproducibility.

## Decision

Project Truss 3 remains one six-skill plugin and introduces profile-specific lifecycle doctrine. Application development retains behavior-oriented contracts. Scientific computing instead proceeds from a question to falsifiable claims, sources/data, formulation, numerical experiment or benchmark, implementation only when needed, scientific review, and evidence-backed GitHub closeout.

The scientific protocol is native Truss behavior. Matt skills remain invoked techniques: research for source uncertainty, domain modeling for language and formulation concepts, prototype for uncertain numerical design, diagnosis for failures, and code review for implementation. TDD runs only for an explicitly durable discrete software contract.

Scientific issue contracts and machine-validatable benchmark/evidence schemas are part of the v3 runtime. Evidence is classified independently of workflow success; a well-supported `FALSIFIED` result is complete. Setup discovers repository-owned scientific paths and commands without imposing a `.scientific` tree or new state store.

## Consequences

- Existing v2 application issues remain expressible through the application profile, but the runtime contract version is a clean v3 cutover.
- Scientific agents cannot begin implementation before establishing the claim and planned evidence.
- Change-detection snapshots may guard locked artifacts but cannot masquerade as independent oracles.
- Scientific work may close without a PR when no implementation change is required and the issue/evidence contracts permit it.
- GitHub, Git, reviews, integration, and current worktrees remain authoritative lifecycle state.
