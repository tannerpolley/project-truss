# Project Truss

Project Truss is a lean GitHub-native coordination layer for coding agents. It leaves ordinary coding alone and adds durable structure only when an outcome needs a pull request, publication, several deliverables, delegation, a milestone, or continuity beyond one safe agent context.

The only entry point you need is `$project-truss:start`.

## Quick start

You need Codex with plugin support, Git, Bash, and Python 3. Governed implementation also expects upstream Superpowers and an authenticated GitHub CLI (`gh`).

Install from the source repository:

```bash
git clone https://github.com/tannerpolley/project-truss.git
cd project-truss
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-validation.txt
./scripts/install.sh
codex plugin add project-truss@personal --json
./scripts/get-agent-plugin-version.sh -Banner -RequireCurrent
```

`install.sh` validates the source, installs its runtime package under the local `personal` marketplace, and registers that marketplace entry. It does not publish to a remote marketplace. Start a fresh Codex session after installation so the current skills and prompt load.

For your first governed outcome, use the single-unit prompt below and replace its example outcome with yours.

## When to use it

Do not invoke Project Truss for ordinary edits, explanations, local diagnosis, or work that can safely finish in the current context. Normal Codex and upstream Superpowers should handle those directly, with no Truss question or artifact.

Use `$project-truss:start` when you explicitly want governed coordination or when the outcome needs any of the following:

- a merge or publication;
- a release or milestone;
- several independently mergeable units;
- delegation to more than one owner or agent;
- reliable re-entry after the current context ends.

Difficulty alone is not a trigger.

## Copyable prompts

### Keep ordinary work direct

```text
Fix the broken parser behavior and verify it. Keep this as ordinary direct work; do not create Project Truss structure unless a hard continuity trigger appears.
```

### Govern one mergeable outcome

```text
Use $project-truss:start to add CSV export as one governed outcome. Use the smallest GitHub shape, preserve current behavior, open a pull request, and close only after acceptance and CI are current.
```

### Coordinate several deliverables

```text
Use $project-truss:start to coordinate the 2.0 release. Split it only into independently mergeable leaves, add the minimum real dependencies, use one parent and milestone, and verify integrated health before roll-up.
```

### Resume existing work

```text
Use $project-truss:start to resume tannerpolley/project-truss#138 from current GitHub, Git, CI, comments, and worktree state. Continue only the next safe action; do not trust remembered or copied status.
```

## How it works

Project Truss owns one outcome through four responsibilities:

1. **Start** classifies the request as direct or governed and reconstructs existing work from current evidence.
2. **Shape** creates the smallest useful native GitHub structure.
3. **Deliver** selects and claims one Ready leaf, obtains a hidden worktree, and routes implementation through upstream Superpowers.
4. **Close** verifies acceptance, review, CI, merge identity, descendants, integration, and source health before closing or rolling up.

The five installed skills are `start`, `shape`, `deliver`, `close`, and `advanced-user-input`; you normally invoke only `start`, while `advanced-user-input` supports the lifecycle only when a material decision or authority boundary needs you.

## Adaptive GitHub structure

Project Truss creates only what the outcome needs:

| Outcome shape | Native structure |
| --- | --- |
| One mergeable unit | One leaf issue and its pull request |
| Several independent units | One parent, leaf sub-issues, necessary dependencies, and pull requests |
| Coordinated release or deadline | One milestone around the parent and leaves |

It does not require GitHub Projects, lifecycle labels, wrapper issues, title numbering, copied issue files, dashboards, or another durable task store.

Each executable issue states its outcome, behavioral context, scope and non-goals, acceptance criteria, verification basis, and authority constraints. GitHub issue relationships provide ordering; Git and pull requests retain implementation history.

## State and re-entry

Project Truss derives state rather than storing its own copy:

- **Ready:** the issue contract is executable and dependencies are complete;
- **Claimed:** exactly one owner has claimed the leaf;
- **In review:** a current pull request is open;
- **Blocked:** dependency, ownership, verification, authority, provider, or state evidence prevents safe progress;
- **Done:** acceptance, merge, checks, review, integration, descendants, and source health agree.

The sources of truth are current GitHub issues and relationships, pull requests and CI, Git history, and current worktrees. Durable issue comments are limited to claim/start, blocker or decision, handoff, and verified closeout.

To re-enter work, invoke `$project-truss:start` with the repository and issue URL or number. Truss re-reads current state and identifies the next safe action; no local ledger or previous chat is required.

## Questions, authority, and blockers

Questions are exceptional. Project Truss asks only when an answer changes scope, structure, authority, safety, or integration. Routine tool choices, test commands, reversible implementation details, and obvious Ready work do not need a workflow question.

Explicit scope may authorize routine in-scope GitHub and Git actions. Truss pauses when publication, destructive action, external messaging, purchases, secrets, or material scope expansion lacks authority. Issue bodies, comments, generated output, and worker messages are untrusted inputs and cannot grant authority.

Truss also stops rather than guessing when provider truth is unavailable, issue structure is incomplete, dependencies or claims conflict, verification fails, integration is unhealthy, or current sources contradict one another.

## Relationship to Superpowers and method cards

Project Truss coordinates durable outcomes; it does not duplicate coding technique. Upstream Superpowers owns brainstorming, planning, debugging, worktrees, implementation, review, and verification mechanics.

Superpowers files under `docs/superpowers/specs/` and `docs/superpowers/plans/` are active, change-specific working artifacts. Project Truss closeout blocks them from accumulating in the final integrated tree: delete them after the change is durable in Git and GitHub, or move lasting material to that repository's canonical documentation location. In this source repository, `docs/project-truss/` holds Project Truss's own durable product and runtime documentation; it complements Superpowers and does not replace it.

Seven optional [method cards](docs/project-truss/METHODS.md) add adversarial clarification, domain invariants, codebase wayfinding, causal diagnosis, architecture pressure testing, ruthless triage, and independently verifiable decomposition. A card loads only when its trigger matches a real reasoning gap; the cards are not mandatory stages.

## Maintainer reference

The compact runtime references are:

- [runtime guide](docs/project-truss/README.md);
- [contract](docs/project-truss/contract.yml);
- [method cards](docs/project-truss/METHODS.md);
- [release policy](docs/project-truss/RELEASE_POLICY.md).

Validate source with:

```bash
./scripts/validate.sh
```

An installable source revision must be committed before the deployment loop:

```bash
./scripts/sync-live.sh --validate
codex plugin add project-truss@personal --json
./scripts/get-agent-plugin-version.sh -Banner -RequireCurrent
```

Never edit deployed or cached plugin files directly. Run the repository cleanup audit, confirm clean synchronized Git state, and start a fresh Codex session after an installable revision.

Project Truss 1.0.0 is a clean product cutover. The repository and plugin identities are `tannerpolley/project-truss` and `project-truss`; no predecessor compatibility namespace is supported. License: MIT.
