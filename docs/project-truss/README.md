# Project Truss runtime contract

Project Truss is the user-facing harness; Matt skills are invoked techniques. Users normally run `project-truss:setup` once and `project-truss:start` thereafter. Intentional entry into `shape`, `resolve`, `close`, or `advanced-user-input` returns control to Start.

GitHub, Git, reviews, integration, and current worktrees are lifecycle truth. Optional provider checks, labels, milestones, Projects, and comments are useful views but do not grant Ready or Done. Truss adds no lifecycle database.

## Repository profiles

Setup records one exact `Repository Profile:` marker and managed guidance. It discovers, but never invents, repository context, scientific data/benchmark/research paths, and validation commands.

- `application-development`: shape observable behavior, use TDD for durable behavior, implement, review Standards and Spec, merge, close.
- `scientific-computing`: shape falsifiable claims, resolve sources/formulation/oracles, run numerical experiments, implement only when needed, review scientific evidence, classify the result, close or merge.
- `general`: retain repository-defined verification behavior.

The scientific benchmark and evidence grammar is defined in [SCIENTIFIC.md](SCIENTIFIC.md).

## Start and lanes

Start reads `CONTEXT.md` or `CONTEXT-MAP.md`, the nearest context, ADRs, profile guidance, Git/GitHub state, and available Matt skills. Plan chooses:

- `direct` for work needing no durable coordination;
- `light` for one standalone issue/PR;
- `governed` for explicit governance, multiple units, delegation, a release/milestone, or unsafe context size.

Every stage returns a continuation token. Start consumes it until direct completion, a named blocker, or truthful closeout. Missing scientific claims or evidence plans route into a focused Start interview; they do not justify silent termination.

An existing PR with no matching Truss resolution receipt stays direct. Truss reviews, merges with authority, and cleans it without manufacturing an issue or receipt.

## GitHub contracts

Application roots use Problem Statement, Solution, User Stories, Implementation Decisions, Testing Decisions, Out of Scope, and Further Notes. Application standalone issues use What to build, Acceptance criteria, and Blocked by; leaves add Parent.

Scientific roots use Scientific Question, Falsifiable Claims, Evidence and Sources, Mathematical or Numerical Formulation, Benchmark and Validation Plan, Acceptance and Falsification Criteria, Out of Scope, and Further Notes. Scientific standalone issues use Claim to Establish, Inputs and Sources, Experiment or Implementation, Acceptance and Falsification Criteria, Required Evidence, and Blocked by; leaves add Parent.

Standalone issues never require parents. Roots/leaves are only for genuine decomposition. One explicitly selected atomic resolution set may share an owner, synchronized implementation base, branch, attached worktree, receipt, and PR; independent issues do not.

Labels are preserved and descriptive. `agent-shaped` is advisory. Milestones represent real coordinated targets. An explicit GitHub Project owner/number may receive idempotent issue/PR memberships through native `gh project`; fields and Status remain non-authoritative.

## Synchronization

Before a resolution branch/worktree, run:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Prepare -RepoRoot .
```

Prepare discovers the canonical checkout, primary remote, and live default branch, fetches with pruning, requires clean state, and advances only by fast-forward. It never assumes `origin/main`, resets, rebases, stashes, or discards work. The returned full commit is the implementation base; Resolve revalidates the exact object supplied as `PreparationJson`.

After a merged PR and deleted remote head, Close runs the exact-outcome Cleanup action. It fetches/prunes, fast-forwards the canonical default, and removes only the clean verified outcome worktree/branch when authorized. Active, protected, dirty, diverged, manually deleted, non-GitHub, mismatched, and unverified branches are retained with reasons. Squash/rebase deletion requires exact merged-PR head proof.

Git 2.43 has no native `post-fetch` hook, and `post-merge` cannot observe a remote GitHub PR merge. Explicit Prepare and Cleanup actions remain the synchronization points.

## Closeout

Application closeout requires checked criteria, repository-selected verification, clear review, healthy integration, source cleanliness, and matching GitHub/Git evidence.

Scientific closeout additionally requires a valid evidence packet and separate judgments for source, formulation, numerical verification, empirical validation, reproducibility, and implementation promotion. `FALSIFIED` is a valid successful classification. A research-only scientific issue may close without a PR when its contract and evidence allow it.

CI/status checks and command-line transcripts are never extra mandatory gates. Failed verification, review, or scientific evidence routes to diagnosis or evidence repair and retry.
