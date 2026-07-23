# Project Truss

Project Truss is a Matt-first, GitHub-native coordination plugin for durable coding outcomes. It adds issue structure, atomic resolution sets, dependency ordering, pull-request continuity, CI-aware closeout, descriptive labels, milestones, and optional GitHub Projects projection while leaving ordinary coding direct.

The canonical product and runtime contract is [docs/project-truss/README.md](docs/project-truss/README.md).

## Requirements

- Codex with plugin support
- Git, Bash, and Python 3
- authenticated GitHub CLI (`gh`)
- Matt Pocock engineering skills and repository setup under `docs/agents/` for governed work

Native `gh project` support is required only when Project projection is explicitly requested. The optional `gh projects` extension is not a runtime dependency.

## Install

```bash
./scripts/install.sh
codex plugin add project-truss@personal --json
```

Start a fresh Codex session after installation.

## Use

Invoke `$project-truss:start` for explicit Truss work or an outcome requiring publication, several deliverables, delegation, a milestone, or continuity beyond one safe context.

```text
Use $project-truss:start to own this outcome through verified merge and closeout.
```

The installed skills are `start`, `shape`, `resolve`, `close`, and `advanced-user-input`.

## Develop and release

```bash
./scripts/validate.sh
./scripts/prepare-release.sh -Version 2.0.0 -CheckOnly
./scripts/sync-live.sh --validate
codex plugin add project-truss@personal --json
./scripts/get-agent-plugin-version.sh -Banner -RequireCurrent
```

Project Truss 2.0 is a clean cutover with no `deliver` alias or v1 issue parser. License: MIT.
