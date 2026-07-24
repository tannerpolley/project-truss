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

When a Project projection is configured, run the Project action with `ensure:false` for every selected issue and the pull request and require `member:true`. It re-checks structured native `gh project item-list` output. Membership is acceptance evidence only and never changes lifecycle state.

Merge the guarded head only with authority. Re-read GitHub after merge, mark acceptance from evidence, close every selected leaf through the shared pull request, and post at most one concise verified closeout receipt per leaf.

## Synchronize and retire local outcome state

After GitHub confirms the guarded pull request merged and its remote head branch is deleted, return to the clean canonical checkout on the discovered default branch and run:

```bash
scripts/project-truss.sh -Action Cleanup -RepoRoot . -Repository OWNER/REPO \
  -CleanupJson '{"pull_request":123,"branch":"codex/issue-123","worktree":"/absolute/outcome-worktree","cleanup_authorized":true}'
```

Cleanup re-discovers the primary remote and default branch, verifies the exact merged pull request and deleted remote head, fetches with pruning, and fast-forwards the canonical default branch before local retirement. It removes only the recorded clean outcome worktree and branch. A graph-merged branch uses normal deletion; a squash/rebase branch uses force deletion only when its local head exactly matches the confirmed merged pull-request head.

Without local cleanup authority, pass `cleanup_authorized:false`; synchronization still occurs and retirement reports `skipped_not_authorized`. Current, protected-default, active elsewhere, dirty, diverged, manually deleted, non-GitHub, or otherwise unverified state remains untouched with a reason. Never replace this with an unguarded `git branch -D` loop. `git sync --delete` and `git clean-gone --delete --no-fetch` remain useful generic Git-skill helpers, but Truss uses the narrower exact-outcome equivalent so unrelated stale branches are outside its authority.

## Roll up

Close the root only after every required child derives Done and integrated repository health is clean. Close a milestone only after all included outcomes are Done. Restore the discovered canonical local default branch, remove only outcome-owned worktrees and branches, and retain GitHub/Git history as the durable record.
