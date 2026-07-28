# ADR 0002: Project Truss is the user-facing engineering facade

## Status

Accepted

## Context

Project Truss coordinates durable outcomes while Matt Pocock skills provide engineering methods. Requiring users to choose between both surfaces leaks routing details, makes command-only Matt workflows appear unavailable, and weakens consistent GitHub issue management.

Wayfinder also creates decision maps and question tickets whose purpose differs from Project Truss execution issues. Treating both taxonomies as lifecycle inputs would introduce ambiguous state.

## Decision

Users invoke `project-truss:setup` once per repository and `project-truss:start` thereafter. Start selects internal Truss stages and routes Matt methods in one of four explicit modes: `invocable`, `facaded`, `missing`, or `not_triggered`.

Setup adopts the Matt repository-setup contract, preserves unrelated instructions, and writes no lifecycle database. Command-only methods may be facaded when Truss has a concrete equivalent contract. Unavailable required methods fail truthfully.

Wayfinder is a facaded pre-Shape decision method. Its maps and question tickets may inform Shape, but Project Truss creates fresh root and leaf issues and derives no state from Wayfinder metadata.

## Consequences

Project Truss becomes the stable public interface while Matt methods remain independently replaceable technique modules. GitHub, Git, CI, and current worktrees remain authoritative. Setup and method routing add no persistent lifecycle store.
