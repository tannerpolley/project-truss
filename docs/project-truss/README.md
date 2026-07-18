# Project Truss Runtime Guide

Project Truss is a lean coordination layer for coding outcomes that need durable continuity. Ordinary work remains direct. Governed work uses GitHub issues, native relationships, pull requests, Git, CI, and current worktrees as its only lifecycle truth.

## Activation

Use `$project-truss:start` only when explicitly requested or when work needs merge or publication, multiple deliverables, delegation, a milestone or deadline, or continuity beyond one safe context. Difficulty alone is not a trigger.

The entry point classifies the request with `scripts/project-truss.sh -Action Plan`, then routes current governed state to shape, deliver, or close. It asks only when a material decision or authority boundary cannot be inferred.

## Durable shape

- one unit: leaf issue plus pull request;
- several units: parent plus leaf sub-issues and necessary dependencies;
- coordinated release or deadline: milestone plus parent and leaves.

Every leaf uses the six headings in `contract.yml`. State is derived as Ready, Claimed, In review, Blocked, or Done. Ready additionally requires all temporary Superpowers shaping inputs to be retired. There is no separate task store.

## Skills

- `start`: direct/governed classification and one-outcome ownership;
- `shape`: adaptive native GitHub structure;
- `deliver`: Ready selection, single claim, feedback, isolation, and upstream execution;
- `close`: verification, merge, roll-up, and artifact retirement;
- `advanced-user-input`: material questions and authority boundaries.

Project Truss delegates coding mechanics to upstream Superpowers and loads method cards from `METHODS.md` only when their triggers match.

## Working artifacts

Superpowers specs and plans under `docs/superpowers/specs/` and `docs/superpowers/plans/` are temporary inputs used only to shape governed work. Shape synthesizes rather than copies them into the smallest native GitHub structure, then re-reads every issue and relationship. It verifies preservation of the outcome, scope and non-scope, architectural or scientific invariants, constraints and tolerances, dependencies, acceptance criteria, and required validation evidence.

If issue creation or verification fails, retain the files while correcting GitHub. Once verification succeeds, GitHub is authoritative: promote lasting insight to the target repository's canonical documentation and delete the duplicate files immediately. Live Status reports exact `unretired_artifacts`, exposes no Ready frontier while the list is non-empty, and blocks claim or implementation.

Deliver records the full pre-branch commit in the claim receipt as `ImplementationBase`. Base-bound Status reports `implementation_artifact_history` when any implementation commit touched a working-artifact path, even after deletion. Both lists must be empty before implementation, before every implementation commit, and before handoff; a contaminated branch must be recreated from its verified base. Closeout repeats the same base-bound checks as defense-in-depth. This prevents temporary files from entering implementation history and aggregate change counts rather than merely deleting them from the final tree.

This plugin's `docs/project-truss/` directory is different: it contains the durable runtime contract and product guidance shipped by Project Truss itself. It complements Superpowers rather than replacing it, and it is not the required destination for documentation in other repositories.
