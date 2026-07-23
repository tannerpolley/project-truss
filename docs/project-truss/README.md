# Project Truss runtime contract

Project Truss is a Matt-first coordination layer for coding outcomes that need durable continuity. Ordinary work remains direct. Governed work uses GitHub issues and native relationships, Git, pull requests, CI, and current worktrees as lifecycle truth.

## Entry and stages

`start` calls `scripts/project-truss.sh -Action Plan` and routes one outcome:

- `shape` grills when required and publishes Matt root/leaf contracts directly to GitHub;
- `resolve` claims one explicit singleton or multi-leaf atomic set in one worktree, branch, and pull request;
- `close` runs shared Standards review, per-ticket Spec review, verification, merge, and roll-up;
- `advanced-user-input` handles only material decisions or authority.

Before governed work, Start verifies the repository's Matt setup and required skill capabilities. Missing capability is `method_capability_missing`. Direct work is not blocked.

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

## Closeout

Close reviews Standards once over the shared diff and Spec once per selected leaf. It requires matching receipts, checked acceptance, one shared PR/head, successful completed CI, clear review state, healthy integration, and clean source state. After merge, every selected leaf must derive Done before the root or milestone closes.
