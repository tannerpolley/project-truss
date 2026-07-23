# Project Truss

Project Truss is a Matt-first, GitHub-native coordination plugin for durable coding outcomes. It adds issue structure, atomic claims, dependency ordering, pull-request continuity, CI-aware closeout, milestones, descriptive labels, and optional GitHub Projects projection while leaving ordinary coding direct.

## Requirements

- Codex with plugin support
- Git, Bash, and Python 3
- authenticated GitHub CLI (`gh`)
- Matt Pocock engineering skills plus repository setup under `docs/agents/` for governed work

Native `gh project` support is required only when a Project projection is explicitly requested. The optional `gh projects` extension is not a runtime dependency.

## Install

```bash
./scripts/install.sh
codex plugin add project-truss@personal --json
```

Start a fresh Codex session after installation.

## Use

Invoke `$project-truss:start` when the user explicitly requests Truss or an outcome needs merge/publication, several deliverables, delegation, a milestone, or continuity beyond one safe context.

```text
Use $project-truss:start to own this outcome through verified merge and closeout.
```

The installed stages are:

- `start`: classify, verify Matt capability, and reconstruct current truth;
- `shape`: grill when required and publish native GitHub root/leaf contracts;
- `resolve`: execute an explicit singleton or multi-leaf atomic set;
- `close`: review, verify, merge, and roll up;
- `advanced-user-input`: resolve one material decision or authority boundary.

## Matt-first workflow

New governed outcomes and material rescope require grilling. Published roots use Matt's Problem Statement, Solution, User Stories, Implementation Decisions, Testing Decisions, Out of Scope, and Further Notes structure. Executable leaves use Parent, What to build, Acceptance criteria, and Blocked by.

Implementation routes by evidence to Matt methods such as TDD, diagnosis, research, domain modeling, prototyping, conflict resolution, and two-axis code review. Project Truss coordinates those methods; it does not copy them or claim unavailable command-oriented methods ran.

## Atomic resolution sets

Resolve defaults to one addressed Ready leaf. Several or all leaves require an explicit list. The selected set receives:

- one owner;
- one full implementation base;
- one hidden worktree;
- one branch;
- one pull request;
- one canonical receipt recorded identically on every member.

Open dependencies inside the set are atomic ordering constraints. An unresolved dependency outside the set blocks work. Partial claims or receipt disagreement fail closed.

## GitHub-native management

GitHub issues, native sub-issues and blocked-by relationships, pull requests, CI, Git, and current worktrees are authoritative.

Descriptive labels are allowed and preserved. The advisory `agent-shaped` label may represent Matt's `ready-for-agent` role, but labels never determine Ready, Claimed, In review, Blocked, or Done.

An explicitly selected GitHub Project can receive root, leaf, and PR memberships through native `gh project` commands. Project fields and Status remain non-authoritative. Project creation, field synchronization, and automatic discovery are out of scope.

## CLI

```bash
./scripts/project-truss.sh -Action Plan -RequestJson '{"explicit":true,"matt_configured":true,"available_methods":["grilling"],"new_outcome":true}'
./scripts/project-truss.sh -Action Status -Repository OWNER/REPO -Issue 123
./scripts/project-truss.sh -Action Resolve -Repository OWNER/REPO -Issue 123 -ResolutionJson '{"issues":[124,125],"owner":"LOGIN","implementation_base":"FULL_SHA","branch":"codex/outcome","worktree":"WORKTREE_ID"}'
```

`Resolve` is read-only policy preflight. Skills perform authorized GitHub and Git mutations, then rerun it with `-RequireRecorded true` to verify the complete set.

## Validation and release

```bash
./scripts/validate.sh
./scripts/prepare-release.sh -Version 2.0.0 -CheckOnly
./scripts/sync-live.sh --validate
codex plugin add project-truss@personal --json
./scripts/get-agent-plugin-version.sh -Banner -RequireCurrent
```

Project Truss 2.0 is a clean cutover: there is no `deliver` alias and the retired v1 issue parser is not retained. License: MIT.
