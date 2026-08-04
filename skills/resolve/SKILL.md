---
name: resolve
description: Use on an explicitly selected Ready standalone issue, leaf, or genuinely atomic set to claim it, invoke only triggered Matt disciplines, implement in the attached checkout, and publish the appropriate pull request before returning to Start.
---

# Project Truss Resolve

Apply `docs/project-truss/contract.yml`. Resolve is the Truss implementation stage: work from published tickets, invoke Matt TDD and other triggered disciplines directly, run focused checks continuously, run the full suite once at the end, perform two-axis review, and return to Start.

## Select and preflight

Default to the addressed standalone issue or leaf. Several issues require an explicit `issues` list; resolve independent issues separately with separate owners/PRs, and use a multi-issue set only when one atomic change truly needs it.

From the clean canonical checkout, run `"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Prepare -RepoRoot .`. Create the attached feature branch or hidden worktree from the exact returned `implementation_base`, never from an unsynchronized local branch. If native Codex worktree attachment is unavailable, keep the feature branch in the task-attached checkout rather than redirecting commands to an unattached worktree.

After creation, verify that the task-visible checkout, command cwd, current branch, Git toplevel, and recorded worktree all identify the same feature checkout. Preserve the exact Prepare JSON as `PreparationJson`; `Claim` can infer the receipt from the attached checkout, current user, and issue when no JSON is supplied. Run:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Resolve -Repository OWNER/REPO -Issue ROOT_OR_LEAF \
  -PreparationJson PREPARE_JSON -ResolutionJson RESOLUTION_JSON
```

Every selected issue must have an executable standalone or leaf contract, no competing owner or pull request, and no unresolved external blocker. Open blockers included in the selected set are internal atomic constraints. Any missing member, partial claim, conflicting receipt, stale base, or shared-field mismatch stops as `claim_conflict` or `state_contradiction`.

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

For independent issues, repeat this flow per issue. Do not create a parent, shared receipt, or shared PR merely to make unrelated work look atomic.

Retain per-leaf Ready, Claimed, In review, Blocked, and Done states. The receipt coordinates the set; it is not a second state store.

## Execute through Matt methods

Use Plan-inferred methods: TDD for stable behavior, diagnosing-bugs for demonstrated failures, research for primary-source uncertainty, domain-modeling for language and invariants, prototype for a throwaway design question, resolving-merge-conflicts for conflicts, code-review before handoff, and cleanup/minimization for high-risk or structural changes. Scientific-computing code also requires `scientific-coding-and-testing`. Missing capability is a governed blocker and a light-lane degradation.

Keep canonical `CONTEXT.md`, ADRs, and useful research notes. Keep prototypes on throwaway branches with a linked verdict. Do not create local issue/spec/plan mirrors.

If the issue records a GitHub Project projection, run the Project action with the linked pull-request URL and `ensure:true`; membership is advisory unless the projection says `required:true`. Project fields remain non-authoritative.

After implementation, handoff, or pull-request creation, return to Start; none is terminal.
