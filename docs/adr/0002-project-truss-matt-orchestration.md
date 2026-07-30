# ADR 0002: Project Truss directly orchestrates Matt methods and native lifecycle

## Status

Accepted

## Context

Project Truss coordinates durable outcomes while Matt Pocock skills provide engineering methods. The workflow needs one normal starting point with durable GitHub lifecycle control, while still allowing every Project Truss stage to be called intentionally and every Matt discipline to remain independently useful.

Wayfinder also creates decision maps and question tickets whose purpose differs from Project Truss execution issues. Treating both taxonomies as lifecycle inputs would introduce ambiguous state.

## Decision

All six Project Truss skills are callable. Users invoke `project-truss:setup` once per repository and normally use `project-truss:start` thereafter. Start directly invokes the installed model-invocable Matt disciplines, selects native Truss stages, and reports method routes as `invocable`, `missing`, or `not_triggered`.

Start is a continuation loop, not a one-stage dispatcher. It re-observes native state after every stage and continues until direct completion, an intentional decision handoff, a named blocker, or verified closeout. New outcomes and material rescope directly use `grilling` with active `domain-modeling`; Shape requires at least one answered decision and explicit shared-understanding confirmation.

Setup adopts the Matt repository-setup contract, preserves unrelated instructions, and writes no lifecycle database. User-invoked Matt wrappers are not silently chained by another user-invoked skill. Unavailable required model-invocable methods fail truthfully.

Wayfinder is a native pre-Shape decision path. Its maps and question tickets may inform Shape, but Project Truss creates fresh root and leaf issues and derives no state from Wayfinder metadata.

## Consequences

Project Truss supplies the stable lifecycle coordinator while Matt methods remain independently replaceable technique modules. Agents cannot treat issue creation, implementation, pull-request creation, CI, review, merge, or pending cleanup as terminal. GitHub, Git, CI, and current worktrees remain authoritative; continuation adds no persistent lifecycle store.
