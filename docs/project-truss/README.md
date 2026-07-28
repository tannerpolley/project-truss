# Project Truss runtime contract

Project Truss is the sole user-facing facade for Matt-first engineering and GitHub-native coordination. Invoke `project-truss:setup` once per repository, then use `project-truss:start` for ongoing work. Ordinary work remains direct. Governed work uses GitHub issues and native relationships, Git, pull requests, CI, and current worktrees as lifecycle truth.

Commands below use `PROJECT_TRUSS_ROOT` for the absolute installed plugin root, resolved from the active Project Truss skill location.

## Entry and stages

`setup` inspects repository truth, proposes the smallest Matt-compatible configuration, confirms material choices, and applies it idempotently:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Setup -RepoRoot . \
  -SetupJson '{"repository":"OWNER/REPO","instruction_file":"AGENTS.md","domain_layout":"single-context","triage_enabled":true,"available_methods":[]}'
```

It preserves unrelated instructions and writes one managed Agent skills block plus the selected `docs/agents/` files. It does not create lifecycle state.

`start` calls `"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Plan` and owns a continuation loop without requiring the user to name internal skills:

- `shape` grills when required and publishes Matt root/leaf contracts directly to GitHub;
- `resolve` claims one explicit singleton or multi-leaf atomic set in one worktree, branch, and pull request;
- `close` runs shared Standards review, per-ticket Spec review, verification, merge, and roll-up;
- `advanced-user-input` handles only material decisions or authority.

Before governed work, Start verifies repository setup and required method capabilities. Missing setup routes to Setup. Each method is reported as `invocable`, `facaded`, `missing`, or `not_triggered`; only a triggered `missing` method blocks governed work. Direct work is not blocked.

Plan infers current Matt shaping, quality, and repository-profile methods. New outcomes and material rescope facade upstream `grill-with-docs` by invoking `grilling` with active `domain-modeling`; at least one one-at-a-time decision and explicit shared-understanding confirmation are required before Shape. Governed code requires code review, surface minimization, and cutthroat cleanup. Stable behavior requires TDD, while scientific-computing code additionally requires `scientific-coding-and-testing`.

Every governed Plan has a non-null `next_action`. After each internal stage, Start re-reads authoritative Status and continues. Failed verification, CI, or review routes through diagnosis, repair, and retry. Intermediate publication, implementation, PR, CI, review, merge, and cleanup-preparation states are never completion.

Wayfinder is a facaded, pre-Shape decision method for outcomes that exceed one safe context. Its map and `## Question` tickets are source context only. Shape creates fresh Project Truss root and leaf issues; Wayfinder metadata never becomes lifecycle evidence.

## Git synchronization

Resolve prepares its implementation base from live Git state before creating a branch or worktree:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Prepare -RepoRoot .
```

Prepare parses current worktrees and tracking configuration to identify the canonical checkout, primary remote, and remote default branch without assuming `origin` or `main`. It requires the canonical checkout to be clean and on that default branch, fetches only the primary remote with pruning, performs a fast-forward-only merge, and requires the local and remote-tracking heads to match. The returned full `implementation_base` is captured only after synchronization.

Dirty, detached, non-default, ahead, diverged, ambiguous, untracked, or unavailable state fails with a canonical blocker. Prepare never resets, rebases, stashes, discards, or silently chooses a fallback. The feature branch/worktree must be created from the returned base. Initial Resolve receives that exact object as `PreparationJson`, revalidates its local-default and remote-tracking refs, and verifies that the invocation cwd, current branch, Git toplevel, and absolute receipt worktree agree.

## Issue contracts

Root specifications use:

1. Problem Statement
2. Solution
3. User Stories
4. Implementation Decisions
5. Testing Decisions
6. Out of Scope
7. Further Notes

Leaf tickets use:

1. Parent
2. What to build
3. Acceptance criteria
4. Blocked by

The former six-heading issue format is not accepted in 2.0.

## Lifecycle truth

Each leaf derives Ready, Claimed, In review, Blocked, or Done from current contracts, dependencies, one assignee, one closing pull request, reviews, CI, and closure evidence. Labels, milestones, and Project fields do not derive state.

The full implementation-base SHA remains the shared diff boundary and stale-head guard. There is no provider-specific planning-artifact scan or second persistent state store.

## Resolution sets

Resolve defaults to the addressed leaf. A set of several or all leaves requires explicit issue selection. Every member must be executable, have no competing claim or PR, and have no open blocker outside the selected set. Dependencies within the set become atomic pull-request constraints.

Every member records one identical canonical receipt: sorted issues, owner, implementation base, branch, worktree, and optional PR. Missing or conflicting receipts stop as `claim_conflict` or `state_contradiction`. GitHub has no multi-issue transaction, so Truss uses full-set preflight and post-write verification and stops on any partial mutation.

## Descriptive labels and Projects

Shape preserves existing labels and may add explicitly requested descriptive labels. The advisory Matt `ready-for-agent` role maps to `agent-shaped`. Lifecycle labels are not created or interpreted as state.

An optional GitHub Project projection requires an explicit owner and project number. Truss uses native `gh project view`, `item-list`, and `item-add`; the `gh projects` extension is optional. It adds missing root, leaf, and PR memberships idempotently, verifies structured output without silent truncation, and records one canonical Project URL in the root's Further Notes. It never creates a Project, changes fields, or uses Project metadata as lifecycle input.

The public Project action executes and verifies one membership at a time:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Project -ProjectionJson '{"owner":"OWNER","project":7,"url":"ISSUE_OR_PR_URL","ensure":true}'
```

## Closeout

Close reviews Standards once over the shared diff and Spec once per selected leaf. It requires matching receipts, checked acceptance, one shared PR/head, successful completed CI, clear review state, healthy integration, and clean source state. After merge, every selected leaf must derive Done before the root or milestone closes.

After GitHub confirms the pull request merged and its remote head branch is deleted, Close returns to the clean canonical default checkout and runs:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Cleanup -RepoRoot . -Repository OWNER/REPO \
  -CleanupJson '{"pull_request":123,"branch":"codex/issue-123","worktree":"/absolute/outcome-worktree","cleanup_authorized":true}'
```

Cleanup fetches/prunes and fast-forwards the discovered default branch again before retirement. Cleanup authority is explicit. It removes only the recorded clean outcome worktree and branch; current branches, protected defaults, ruleset-governed branches, worktree-active branches, dirty worktrees, mismatched heads, non-primary-remote branches, and unverified state are skipped with a reason. Graph-merged branches use ancestry-checked compare-and-delete. Squash/rebase branches use the same expected-head guard only after the exact GitHub PR is confirmed merged, the remote head is absent, and the local head matches the merged PR head.

The generic Git skill may use `git sync --delete` or `git clean-gone --delete --no-fetch` for authorized repository-wide cleanup. Project Truss intentionally uses a narrower exact-outcome equivalent so it cannot retire unrelated branches. If required Git or GitHub evidence is unavailable, Cleanup fails loudly.

Git 2.43 has no native `post-fetch` hook, so Project Truss does not install one. A `post-merge` hook is also incomplete because it observes local merge/pull paths, not a remote GitHub PR merge. Explicit Prepare and Cleanup lifecycle actions are the authoritative synchronization points; no hook or second lifecycle database is added.
