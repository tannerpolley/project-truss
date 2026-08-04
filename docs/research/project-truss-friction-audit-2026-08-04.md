# Project Truss friction audit

Date: 2026-08-04

Status: implementation follow-up completed in the working tree; this report
remains the rationale and restriction inventory for the change. It does not
authorize a commit, deployment, issue mutation, or plugin refresh.

## Executive finding

Project Truss is safest where it proves a destructive or irreversible fact: the
merged pull request, exact head, clean source, current worktree, and GitHub/Git
identity. It is most friction-heavy where it turns a useful convention into a
hard capability gate: every explicit request becoming governed, mandatory
interviews and method bundles, manual claims, exact issue schemas, one shared
PR for a set, and provider truncation being treated as unavailable state.

The right direction is an adaptive three-lane workflow:

1. **Direct** for ordinary small work.
2. **Light** for one tracked change that needs an issue and PR but not a full
   resolution set, receipt, parent issue, or milestone.
3. **Governed** for multi-unit, delegated, release, high-risk, or explicitly
   governed work.

The light lane should still use GitHub, Git, Matt methods, review, and safe
cleanup. It should remove ceremony, not evidence. The governed lane should
retain the current fail-closed proof model.

An issue does not need to be in a parent/leaf hierarchy. A self-contained
standalone issue may carry its own scope, acceptance criteria, dependencies,
claim, and pull request. Parent issues and child leaves are for genuinely
decomposed or coordinated work, not a universal ticket shape.

## Scope and method

I inspected the runtime policy, GitHub and Git adapters, command surface,
workspace isolation, all six Project Truss skills, the runtime contract and
ADRs, setup templates, and behavior tests. The hard-trigger and blocker
vocabulary is defined in [`contract.yml`](../project-truss/contract.yml),
planned in [`truss_policy.py`](../../scripts/lib/truss_policy.py#L161-L215),
and protected by the lifecycle tests in `tests/`.

I compared those rules with current primary documentation. GitHub describes
issues as flexible, supports sub-issues, dependencies, labels, milestones,
Projects, issue types, and several creation paths ([Using issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues),
[sub-issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues),
[dependencies](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies)).
GitHub GraphQL explicitly expects clients to traverse pages rather than treat
`hasNextPage` as incapability ([pagination guide](https://docs.github.com/en/graphql/guides/using-pagination-in-the-graphql-api)).
Matt's current guidance emphasizes small, composable methods, a user-invoked
orchestration layer, and model-invoked reusable disciplines ([Matt Pocock
skills README](https://github.com/mattpocock/skills/blob/main/README.md)).

## Restriction inventory

Priority means: P0 = highest friction with a safe, near-term fix; P1 = useful
policy change after the basic UX work; P2 = optional product flexibility.

| ID | Current restriction | Friction | Recommendation |
|---|---|---|---|
| R1 | `explicit` is a hard governance trigger; governed work always gets a leaf and PR, even for one small change. [`truss_policy.py`](../../scripts/lib/truss_policy.py#L161-L178) | A user asking for a concrete one-file fix can be forced into Shape, claim, receipt, worktree, review, merge, and cleanup ceremony. | **P0:** add an adaptive `direct/light/governed` mode. Keep full governance for multi-unit, delegated, release, high-risk, or explicit opt-in work. |
| R2 | Every new governed outcome or material rescope requires both grilling and domain modeling, answered decisions, and explicit confirmation before Shape. [`start/SKILL.md`](../../skills/start/SKILL.md#L18-L22) | Clear, already-specified requests still incur an interview and a confirmation stop. | **P0:** run a completeness check. Skip the interview when scope, acceptance, constraints, and decision are already explicit; otherwise ask one concise question. Preserve the hard stop for genuine ambiguity. |
| R3 | Any governed code change infers `code-review`, `cutthroat-code-cleanup`, and `minimize-code-surface`; stable behavior also infers TDD. [`truss_policy.py`](../../scripts/lib/truss_policy.py#L179-L189) | A tiny typo, fixture, or mechanical change can be made to satisfy a full method bundle. | **P0:** route methods by risk and seam. Keep review before publication; use cleanup/minimization for structural or non-trivial diffs; use TDD at an agreed behavior seam. This matches Matt's composable-method model. |
| R4 | A triggered but unavailable Matt method blocks governed work. [`METHODS.md`](../../docs/project-truss/METHODS.md#L37-L41) | Installation drift or a nonessential unavailable method stops otherwise safe work. | **P0:** distinguish `required`, `recommended`, and `unavailable`. Hard-block only when the missing method protects a stated risk; otherwise continue with a visible degraded-capability finding and a waiver recorded in the PR. |
| R5 | Setup requires a matching GitHub identity and authenticated `gh`, an exact instruction-file choice, and correct monorepo layout signals. [`truss_setup.py`](../../scripts/lib/truss_setup.py#L96-L113), [`setup/SKILL.md`](../../skills/setup/SKILL.md#L19-L32) | First use has a long preflight before the agent can even inspect or implement a small change. | **P0:** make setup read-only and auto-detect by default; write only the bounded managed sections after confirmation. Permit a light lane to report “not configured” without blocking direct work. |
| R6 | Root and leaf issue bodies use strict exact heading sets; mixed or extra headings invalidate a contract. [`truss_policy.py`](../../scripts/lib/truss_policy.py#L646-L689) | Existing useful GitHub issues must be rewritten to fit the parser, and users cannot add harmless context headings. | **P1:** accept canonical headings plus extra headings, normalize common aliases, and report missing semantic content. Keep acceptance and parent/dependency references strict where they affect state. |
| R7 | Wayfinder question/map issues can inform Shape but may never be promoted or reused as execution issues. [`shape/SKILL.md`](../../skills/shape/SKILL.md#L8-L22) | A decision ticket may be duplicated into a fresh root/leaf, creating avoidable issue churn. | **P2:** add explicit `promote`/`adopt` with provenance and contract validation. Never infer authority from Wayfinder metadata automatically. |
| R8 | Claiming a set is a manual optimistic transaction: one owner, identical full receipt on every issue, re-read every member, then one worktree, branch, and PR. [`resolve/SKILL.md`](../../skills/resolve/SKILL.md#L27-L39), [`truss_policy.py`](../../scripts/lib/truss_policy.py#L481-L537) | Agents frequently stop between preflight, assignment, comment, verification, and implementation; recovery from a partial claim is awkward. | **P0:** add a first-class `Claim` or `Resolve --claim` operation. It should preflight, assign, write receipts, verify, and report partial writes with rollback/repair guidance. Keep the same optimistic safety checks. |
| R9 | A resolution set requires one sole assignee and one shared PR/head/branch/worktree. [`truss_policy.py`](../../scripts/lib/truss_policy.py#L503-L518), [`close/SKILL.md`](../../skills/close/SKILL.md#L19-L25) | Independent leaves cannot progress or close through separate PRs; pair/team ownership is rejected. | **P1:** retain the shared-set mode for genuinely atomic work, but permit independent leaves with independent PRs under one parent. Add optional accountable-owner plus collaborators instead of treating multiple assignees as contradiction. |
| R10 | Prepare must run from a clean canonical checkout on the discovered default branch and fast-forward that checkout before any base is captured. [`git_lifecycle.py`](../../scripts/lib/git_lifecycle.py#L134-L192), [`start/SKILL.md`](../../skills/start/SKILL.md#L38-L48) | A user's harmless local change, ahead default branch, or current non-default checkout blocks work even when a separate clean checkout could safely create the feature branch. | **P1:** retain strict canonical mutation rules, but add a read-only prepare path that creates from the fetched remote-tracking default without switching or changing a clean attached feature checkout. Never reset, stash, rebase, or discard. |
| R11 | Cleanup requires merged GitHub proof, a deleted remote head, synchronized canonical default, exact local head/tracking/worktree identity, and explicit cleanup authority. [`git_lifecycle.py`](../../scripts/lib/git_lifecycle.py#L292-L406) | Closeout can stop after a PR is merged because the user must manually return to default, delete the remote branch, and supply an exact absolute worktree path. | **P0:** let Cleanup perform the safe canonical checkout transition when clean; accept an already-absent remote head as satisfied when exact PR/head evidence proves it; derive the recorded worktree where possible. Keep every dirty/current/protected/diverged/unverified skip. |
| R12 | Multiple remotes are ambiguous unless exactly one tracked default candidate remains or `remote.pushDefault` selects one. [`git_lifecycle.py`](../../scripts/lib/git_lifecycle.py#L134-L152) | Common fork/upstream setups become a blocker even when Git has enough safe preference signals. | **P1:** preference order: `branch.<default>.pushRemote`, `remote.pushDefault`, current branch upstream, `origin`, then ask on true ambiguity. Report the selected evidence. |
| R13 | GraphQL connections are fetched with fixed sizes (`assignees:10`, several relations/comments:100, closing PRs:20), and any next page raises `github_capability_missing`. [`truss_github.py`](../../scripts/lib/truss_github.py#L18-L34), [`_connection`](../../scripts/lib/truss_github.py#L174-L183) | Large but valid issues become unreadable to Truss; this is a provider-client limit, not missing GitHub capability. | **P0:** cursor-paginate each required connection with a bounded safety limit and a truthful “scope exceeded” finding only after the limit. Cache per-snapshot pages to avoid repeated calls. |
| R14 | Project membership reads up to 1,000 items and fails when `totalCount != len(items)`. [`truss_github.py`](../../scripts/lib/truss_github.py#L62-L87) | A large Project blocks even when the target item could be found with a filtered query or direct API lookup. | **P1:** use `gh project item-list --query` or cursor pagination and verify the target membership directly. Keep Projects optional and non-authoritative. GitHub CLI documents `--limit` and `--query` for this command ([manual](https://cli.github.com/manual/gh_project_item-list)). |
| R15 | Closeout requires a caller-supplied exact `HealthJson` with verification, integration, source cleanliness, head SHA, and review fields. [`truss_policy.py`](../../scripts/lib/truss_policy.py#L334-L350), [`commands/project.py`](../../scripts/lib/commands/project.py#L235-L267) | Agents assemble ceremony-heavy JSON and can fail on evidence formatting rather than the actual result. | **P0:** add `--auto-health`: derive source cleanliness, current head, merged PR/head, review, and configured verification from live state; ask only for genuinely external integration evidence. Keep explicit health overrides auditable. |
| R16 | Parent and milestone rollups require every child to be closed and `Done`; there is no `Cancelled`, `Deferred`, or `Won't do` terminal state. [`truss_policy.py`](../../scripts/lib/truss_policy.py#L706-L777), [`close/SKILL.md`](../../skills/close/SKILL.md#L40-L44) | A deliberately dropped or superseded child keeps a parent/milestone open forever or encourages dishonest closure. | **P1:** add explicit terminal dispositions with a rollup policy: `Done`, `Cancelled`, and `Deferred` may be acceptable when recorded on the child and excluded from required scope. |
| R17 | Labels, milestones, and Project fields are descriptive only; lifecycle labels are prohibited, and Projects may be acceptance evidence when configured. [`README.md`](../../docs/project-truss/README.md#L70-L89) | Users cannot use familiar GitHub routing/status metadata as a convenience view, and configured Project membership adds closeout work. | **P1:** keep these fields non-authoritative, but allow them as advisory routing/status hints and make Project membership best-effort unless the user selects “required.” Lifecycle truth must still come from contracts, relationships, claims, PRs, and Git. |
| R18 | The public command surface requires `-Action`, exact JSON objects or paths, explicit repository/issue values, and several stage-specific artifacts. [`commands/project.py`](../../scripts/lib/commands/project.py#L141-L269), [`command_support.py`](../../scripts/lib/command_support.py#L81-L158) | The safe core is hard to use manually, and agents stop because they do not know the next artifact to construct. | **P0:** keep strict machine schemas internally but add ergonomic wrappers such as `truss start --issue 123`, `truss claim 123`, `truss close 123`, defaults from the current repo, and one error remediation plus next action. |
| R19 | Workspace isolation receipts require exact provider, task/thread, absolute identity, 40-character head, mode, binding, and publication rules. [`workspace_isolation.py`](../../scripts/lib/workspace_isolation.py#L13-L19, [`workspace_isolation.py`](../../scripts/lib/workspace_isolation.py#L71-L117) | Native-task and local-worktree differences leak into ordinary user flow; a missing provider signal can stop work. | **P1:** preserve exact identity checks but make the receipt generated by the workspace adapter, not hand-authored by the agent. Allow a stable workspace ID plus derived paths instead of requiring users to copy absolute paths. |
| R20 | Every stage tells the agent to return to Start and Start re-observes everything; intermediate publication, implementation, PR, review, merge, and pre-cleanup are explicitly non-terminal. [`start/SKILL.md`](../../skills/start/SKILL.md#L32-L36), [`README.md`](../../docs/project-truss/README.md#L27-L31) | This is correct as a state model but can produce stop/start loops; an agent may return control after one stage without executing the named next action. | **P0:** make each stage emit a structured continuation token containing `next_skill`, `next_action`, evidence, and safe retry count. Start should consume it automatically in the same turn until a real decision/authority blocker or terminal state. |
| R21 | Governed work is GitHub-native and rejects non-GitHub primary remotes. [`docs/agents/issue-tracker.md`](../../docs/agents/issue-tracker.md#L1-L16), [`git_lifecycle.py`](../../scripts/lib/git_lifecycle.py#L329-L334) | This is an intentional Project Truss product boundary, not a defect: GitHub Issues, PRs, relationships, and `gh` are the authoritative coordination surface. | **Non-goal:** keep GitHub as the only supported tracker/hosting authority. Do not add non-GitHub adapters or weaken GitHub proof. |
| R22 | The governed issue model is shaped around root/leaf contracts, and the leaf contract requires a `Parent` reference. [`contract.yml`](../project-truss/contract.yml#L11-L23), [`truss_policy.py`](../../scripts/lib/truss_policy.py#L646-L689) | A simple outcome can require an artificial parent or be rejected as a non-executable issue, adding hierarchy and issue-creation work with no coordination benefit. | **P0:** support a first-class standalone issue contract. Require scope, acceptance, and dependency semantics, but make `Parent` optional when the issue is not a child. Use parent/leaf structure only when there are multiple coordinated outcomes. |

## Restrictions that are already removed

Three concerns from earlier iterations are no longer hard gates:

- CI and status checks are optional provider context, not a merge or closeout
  requirement ([`README.md`](../../docs/project-truss/README.md#L1-L3),
  [`close/SKILL.md`](../../skills/close/SKILL.md#L19-L25)).
- An unclaimed standalone PR may follow the ordinary direct review, merge, and
  cleanup path; it does not need a synthetic Truss leaf or receipt
  ([`start/SKILL.md`](../../skills/start/SKILL.md#L12-L16),
  [`close/SKILL.md`](../../skills/close/SKILL.md#L6-L8)).
- Descriptive labels are allowed and preserved. Only lifecycle interpretation
  is prohibited; labels such as `bug`, area, and priority remain available
  ([`shape/SKILL.md`](../../skills/shape/SKILL.md#L24-L28),
  [`docs/agents/triage-labels.md`](../../docs/agents/triage-labels.md#L1-L13)).

## What should remain strict

These are safety properties, not usability friction, and should not be relaxed:

- Never reset, rebase, auto-stash, discard, or guess a default branch during
  Prepare or Cleanup.
- Never delete the current branch, a protected/default branch, a dirty
  worktree, an active linked worktree, or an unverified manually deleted
  branch.
- Require exact GitHub proof for a merged PR and its head repository, branch,
  and head SHA before non-graph-merged deletion; this covers squash and rebase
  merges.
- Keep GitHub, Git, reviews, integration evidence, and current worktrees as
  the authority. Labels, milestones, Projects, comments, and receipts may
  coordinate evidence but must not become a second lifecycle database.
- Keep acceptance criteria and dependency evidence meaningful. A tolerant
  parser must not turn absent acceptance or an open external dependency into
  readiness.
- Keep direct work available. Truss should not force a governed lifecycle when
  the user has not requested durable issue/PR coordination.

## Recommended implementation order

### P0: remove ceremony without changing safety

1. Add adaptive direct/light/governed planning.
2. Add ergonomic wrappers and a durable continuation token consumed by Start.
3. Implement `Claim`/`Resolve --claim` and auto-generated receipts.
4. Add auto-derived health and safe Cleanup transition handling.
5. Add GraphQL and Project pagination.
6. Replace method bundles with risk-triggered method routing and explicit
   degraded-capability reporting.
7. Allow a standalone governed issue without synthesizing a parent or requiring
   a `Parent` heading; retain parent/leaf rollups for actual issue hierarchies.

### P1: improve native GitHub compatibility

1. Make the issue parser tolerant of extra headings and common aliases while
   preserving semantic checks.
2. Add independent-PR resolution sets, optional collaborators, and explicit
   Cancelled/Deferred child dispositions.
3. Improve multi-remote selection and make Project membership advisory by
   default.
4. Generate workspace receipts from the selected workspace provider.

### P2: optional product breadth

1. Add explicit Wayfinder promotion with provenance only if direct adoption becomes a user requirement; it is not needed for the normal pre-Shape flow.

Project Truss remains GitHub-only. Non-GitHub tracker/provider adapters are a permanent non-goal for this product and are not part of the roadmap.

## How to measure whether friction improved

Add usability measurements rather than only more unit tests:

- time and command count from Start to first edit;
- number of user questions for already-complete requests;
- number of manual claim/receipt mutations;
- percentage of Start runs that stop without a named blocker or terminal
  state;
- provider failures caused by pagination or Project size;
- percentage of cleanup runs that require manual branch/worktree preparation;
- safety regression counts for dirty, diverged, active, protected, wrong-head,
  and unverified deletion cases.

The target is fewer steps and fewer false blockers with zero increase in
unsafe mutation or unverified closeout.

## Implementation follow-up

The current follow-on implements the P0 recommendations and the concrete P1
GitHub-native improvements: adaptive lanes, conditional grilling and method
routing, setup preview/apply, ergonomic action aliases and inferred defaults,
standalone contracts, tolerant headings, first-class claims, continuation
tokens, auto-health, bounded GraphQL pagination, advisory labels and Projects,
collaborator receipts, independent-resolution guidance, terminal dispositions,
workspace receipts, cleanup transition handling, and multi-remote discovery.

The strict canonical Prepare invariant remains intentional: it must capture a
base only after a clean canonical default branch has been fetched and
fast-forwarded. A remote-only shortcut was considered and removed because it
would weaken that required safety contract. Wayfinder promotion remains
conditional P2 work, not hidden behavior; non-GitHub adapters are explicitly
out of scope.

## Baseline and validation

At audit time, `./scripts/validate.sh` passed with 77 tests. The implementation
follow-up now passes 85 tests plus runtime package, skill metadata, release
wiring, and slimming checks. The report does not authorize a commit,
deployment, issue mutation, or plugin refresh.
