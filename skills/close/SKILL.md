---
name: close
description: Use when Project Truss must review, verify, merge, roll up, and retire a governed singleton or resolution set from fresh evidence.
---

# Project Truss Close

Apply `docs/project-truss/contract.yml`. Re-read every selected leaf, canonical receipt, assignee, dependency, human comment, closing pull request, review state, check run, current head, worktree, and optional Project target.

## Two-axis review

Use Matt `code-review` against the recorded implementation base:

- run Standards once over the shared diff using repository instructions plus the smell baseline;
- run Spec separately against every selected leaf and attribute each finding to that ticket.

Do not merge with unresolved findings. A missing required review method is `method_capability_missing`.

## Prove and merge the set

Run repository-profile-selected verification and the full test suite. Require one shared pull request and head SHA, checked acceptance on every leaf, completed successful CI, no changes requested, a clean source tree, healthy integration, one owner, and matching receipts everywhere. Re-run `Resolve` with the pull-request number and `-RequireRecorded true`, then run set-level Closeout health bound to the pull-request head.

When a Project projection is configured, re-check every selected issue and the pull request through structured native `gh project item-list` output. Membership is acceptance evidence only and never changes lifecycle state.

Merge the guarded head only with authority. Re-read GitHub after merge, mark acceptance from evidence, close every selected leaf through the shared pull request, and post at most one concise verified closeout receipt per leaf.

## Roll up

Close the root only after every required child derives Done and integrated repository health is clean. Close a milestone only after all included outcomes are Done. Restore canonical local `main`, remove only outcome-owned worktrees and branches, and retain GitHub/Git history as the durable record.
