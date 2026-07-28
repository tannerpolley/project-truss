# Project Truss

Project Truss is the user-facing facade for Matt-first engineering and GitHub-native coordination. It adds issue structure, atomic resolution sets, dependency ordering, pull-request continuity, CI-aware closeout, descriptive labels, milestones, and optional GitHub Projects projection while leaving ordinary coding direct.

The canonical product and runtime contract is [docs/project-truss/README.md](docs/project-truss/README.md).

## Requirements

- Codex with plugin support
- Git, Bash, and Python 3
- authenticated GitHub CLI (`gh`)
- Matt Pocock engineering skills, routed behind Project Truss

Native `gh project` support is required only when Project projection is explicitly requested. The optional `gh projects` extension is not a runtime dependency.

## Install

```bash
./scripts/install.sh
codex plugin add project-truss@personal --json
```

Start a fresh Codex session after installation.

## Use

Invoke `$project-truss:setup` once per repository, then `$project-truss:start` for engineering work. Start selects Matt methods and internal Truss stages; users do not need to invoke those implementation skills directly.

```text
Use $project-truss:setup to configure this repository.
Use $project-truss:start to own this outcome through verified merge and closeout.
```

The installed skills are `setup`, `start`, `shape`, `resolve`, `close`, and `advanced-user-input`; only Setup and Start are user-facing entrypoints.

## Develop and release

```bash
./scripts/validate.sh
./scripts/prepare-release.sh -Version 2.0.0 -CheckOnly
./scripts/sync-live.sh --validate
codex plugin add project-truss@personal --json
./scripts/get-agent-plugin-version.sh -Banner -RequireCurrent
```

Project Truss 2.0 is a clean cutover with no `deliver` alias or v1 issue parser. License: MIT.
