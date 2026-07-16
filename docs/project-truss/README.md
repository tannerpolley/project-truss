# Project Truss Runtime Guide

Project Truss is a lean coordination layer for coding outcomes that need durable continuity. Ordinary work remains direct. Governed work uses GitHub issues, native relationships, pull requests, Git, CI, and current worktrees as its only lifecycle truth.

## Activation

Use `$project-truss:start` only when explicitly requested or when work needs merge or publication, multiple deliverables, delegation, a milestone or deadline, or continuity beyond one safe context. Difficulty alone is not a trigger.

The entry point classifies the request with `scripts/project-truss.sh -Action Plan`, then routes current governed state to shape, deliver, or close. It asks only when a material decision or authority boundary cannot be inferred.

## Durable shape

- one unit: leaf issue plus pull request;
- several units: parent plus leaf sub-issues and necessary dependencies;
- coordinated release or deadline: milestone plus parent and leaves.

Every leaf uses the six headings in `contract.yml`. State is derived as Ready, Claimed, In review, Blocked, or Done. There is no separate task store.

## Skills

- `start`: direct/governed classification and one-outcome ownership;
- `shape`: adaptive native GitHub structure;
- `deliver`: Ready selection, single claim, feedback, isolation, and upstream execution;
- `close`: verification, merge, roll-up, and artifact retirement;
- `advanced-user-input`: material questions and authority boundaries.

Project Truss delegates coding mechanics to upstream Superpowers and loads method cards from `METHODS.md` only when their triggers match.
