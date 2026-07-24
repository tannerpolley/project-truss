---
name: resolve
description: Use when Project Truss should claim and execute one explicitly selected Ready leaf or atomic set in one hidden worktree and pull request.
---

# Project Truss Resolve

Apply `docs/project-truss/contract.yml`. Resolve is Truss's implementation entrypoint and adopts Matt's implement contract: work from published tickets, use TDD at approved public seams, run focused checks continuously, run the full suite once at the end, then perform two-axis review.

## Select and preflight

Default to the addressed leaf. Several or all leaves require an explicit `issues` list; never infer a multi-leaf set.

From the clean canonical checkout, run `scripts/project-truss.sh -Action Prepare -RepoRoot .`. Create the attached feature branch or hidden worktree from the exact returned `implementation_base`, never from an unsynchronized local branch. If native Codex worktree attachment is unavailable, keep the feature branch in the task-attached checkout rather than redirecting commands to an unattached worktree.

After creation, verify that the task-visible checkout, command cwd, current branch, Git toplevel, and recorded worktree all identify the same feature checkout. Preserve the exact Prepare JSON as `PreparationJson`, and build one `ResolutionJson` object with sorted issues, owner, the Prepare implementation base, branch, absolute worktree identity, and optional pull-request number. Initial preflight revalidates the preparation against live local/default and remote-tracking refs. Run:

```bash
scripts/project-truss.sh -Action Resolve -Repository OWNER/REPO -Issue ROOT_OR_LEAF \
  -PreparationJson PREPARE_JSON -ResolutionJson RESOLUTION_JSON
```

Every selected leaf must have an executable Matt leaf contract, no competing owner or pull request, and no unresolved external blocker. Open blockers included in the selected set are internal atomic constraints. Any missing member, partial claim, conflicting receipt, stale base, or shared-field mismatch stops as `claim_conflict` or `state_contradiction`.

Prepare fails closed when the canonical checkout is dirty, not on the discovered remote default branch, ahead, diverged, or unable to fast-forward. Do not reset, rebase, auto-stash, discard work, or substitute a guessed default branch or remote.

## Claim one atomic set

GitHub cannot mutate several issues transactionally, so use optimistic atomicity:

1. preflight the complete set from live GitHub;
2. capture one full implementation-base commit;
3. assign the same single owner as the sole assignee on every member;
4. record the identical canonical resolution receipt on every member;
5. re-read the complete set with `-RequireRecorded true`;
6. stop implementation if any write or verification is partial;
7. create one hidden worktree, one branch, and one pull request for the set.

Retain per-leaf Ready, Claimed, In review, Blocked, and Done states. The receipt coordinates the set; it is not a second state store.

## Execute through Matt methods

Use only methods triggered by the work: TDD for stable behavior, diagnosing-bugs for demonstrated failures, research for primary-source uncertainty, domain-modeling for language and invariants, prototype for a throwaway design question, resolving-merge-conflicts for conflicts, and code-review before handoff. Missing required capability produces `method_capability_missing`.

Keep canonical `CONTEXT.md`, ADRs, and useful research notes. Keep prototypes on throwaway branches with a linked verdict. Do not create local issue/spec/plan mirrors.

If the root records a GitHub Project projection, run the Project action with the linked pull-request URL and `ensure:true`. It uses native `gh project item-add` idempotently and verifies membership. Project fields remain non-authoritative.
