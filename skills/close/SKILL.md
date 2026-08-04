---
name: close
description: Use after implementation or any pull request to invoke triggered Matt review, verify GitHub/Git evidence, merge or roll up the outcome, retire local state safely, and return to Start.
---

# Project Truss Close

Apply `docs/project-truss/contract.yml`. Close is the evidence and retirement stage. A standalone issue/PR may close directly; governed work uses its recorded issue set. Invoke Matt `code-review` when the change is published, re-read provider truth, complete the correct merge path, then return to Start. No CI or command-line evidence is an extra hard gate.

## Two-axis review

Use Matt `code-review` against the recorded implementation base when Plan triggers it:

- run Standards once over the shared diff using repository instructions plus the smell baseline;
- run Spec separately against every selected leaf and attribute each finding to that ticket.

Do not merge with unresolved findings. A missing governed review method is `method_capability_missing`; a light-lane degradation is reported and does not become a fake blocker.

## Prove and merge the governed resolution

Run repository-profile-selected verification and the full test suite when the lane calls for it. Governed sets require one shared pull request and head SHA, checked acceptance on every selected issue, no changes requested, a clean source tree, healthy integration, one owner, and matching receipts. Independent issues use their own PR evidence. CI/status checks may be retained as optional provider context but are not a closeout gate. Closeout derives health automatically unless explicit external evidence is supplied.

When a Project projection is configured, run the Project action with `ensure:false` for every selected issue and the pull request. Membership is advisory unless explicitly marked required; it never changes lifecycle state.

Merge the guarded head only with authority. Re-read GitHub after merge, mark acceptance from evidence, close every selected leaf through the shared pull request, and post at most one concise verified closeout receipt per leaf.

## Synchronize and retire local outcome state

After GitHub confirms the guarded pull request merged and its remote head branch is deleted, return to the clean canonical checkout on the discovered default branch and run:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Cleanup -RepoRoot . -Repository OWNER/REPO \
  -CleanupJson '{"pull_request":123,"branch":"codex/issue-123","cleanup_authorized":true}'
```

Cleanup re-discovers the primary remote and default branch, verifies the exact merged pull request and deleted remote head, fetches with pruning, and fast-forwards the canonical default branch before local retirement. If the canonical checkout is cleanly on the outcome branch, it returns it to default automatically; the worktree path is derived when possible. It removes only the recorded clean outcome worktree and branch. Graph-merged and squash/rebase branches use expected-head compare-and-delete; non-graph deletion additionally requires the exact confirmed merged pull-request head.

Without local cleanup authority, pass `cleanup_authorized:false`; synchronization still occurs and retirement reports `skipped_not_authorized`. Current, protected-default, active elsewhere, dirty, diverged, manually deleted, non-GitHub, or otherwise unverified state remains untouched with a reason. Never replace this with an unguarded `git branch -D` loop. `git sync --delete` and `git clean-gone --delete --no-fetch` remain useful generic Git-skill helpers, but Truss uses the narrower exact-outcome equivalent so unrelated stale branches are outside its authority.

## Roll up

Close the root only after every required child derives Done; explicitly Cancelled or Deferred children are terminal when the root's scope records that disposition. Close a milestone only after all included outcomes are terminal. Restore the discovered canonical local default branch, remove only outcome-owned worktrees and branches, and retain GitHub/Git history as the durable record.

Return to Start after every review, retry, merge, Cleanup, or roll-up step. Only verified closeout is terminal.
