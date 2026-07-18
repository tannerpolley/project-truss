---
name: deliver
description: Use when Project Truss should claim and execute one Ready GitHub leaf with isolated ownership and current feedback.
---

# Project Truss Deliver

Apply `docs/project-truss/contract.yml`. Run `scripts/project-truss.sh -Action Status` against live GitHub and select only a Ready leaf from the returned frontier.

## Claim one leaf

Require live Status to return an empty `unretired_artifacts` list before adding an assignee or claim comment. A non-empty list means shaping is incomplete: return to Shape for authoritative issue verification and artifact retirement. Do not claim the leaf, create an implementation branch or worktree, or begin implementation while any listed file remains.

Before implementation:

1. re-read dependencies, assignees, linked pull requests, and current worktrees;
2. read human comments newer than the last material transition;
3. capture the full current `HEAD` commit as the implementation base;
4. add exactly one assignee and one concise claim/start comment that includes that base;
5. re-read live state and stop on a claim conflict;
6. obtain one Codex-managed hidden worktree and one issue branch;
7. re-run live Status with `-ImplementationBase <full-base-commit>` and require both `unretired_artifacts` and `implementation_artifact_history` to be empty.

Repeat the base-bound Status check before every implementation commit and before handoff. Current files block through `unretired_artifacts`; a file committed and later deleted still blocks through `implementation_artifact_history`. Stop and recreate the issue branch from its verified base if history is contaminated; deletion from the current tree does not repair implementation history or change counts.

Never infer readiness from a copied queue, stale summary, or closed blocker alone.

## Execute through upstream mechanics

Project Truss owns coordination, not coding technique. Use the nearest repository profile for verification policy and invoke only the upstream Superpowers mechanics the leaf needs, such as brainstorming, writing or executing plans, systematic debugging, worktrees, review, and verification before completion.

Load a card from `docs/project-truss/METHODS.md` only when its Trigger matches a concrete reasoning gap. Do not turn cards into mandatory stages.

Keep durable comments to claim/start, blocker or decision, handoff, and verified closeout. Commits, tests, and play-by-play stay in Git and the pull request. Re-run base-bound Status after material external changes and before handoff.

Stop for an unresolved dependency, competing owner, new feedback that changes scope, missing authority, failed repository-selected verification, or unavailable provider truth.
