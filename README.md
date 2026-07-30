# Project Truss

Project Truss coordinates Matt-first engineering with GitHub-native lifecycle control. It adds issue structure, atomic resolution sets, dependency ordering, pull-request continuity, CI-aware closeout, descriptive labels, milestones, and optional GitHub Projects projection while leaving ordinary coding direct.

The canonical product and runtime contract is [docs/project-truss/README.md](docs/project-truss/README.md).

## Requirements

- Codex with plugin support
- Git, Bash, and Python 3
- authenticated GitHub CLI (`gh`)
- Matt Pocock engineering skills, invoked directly when their discipline is needed

Native `gh project` support is required only when Project projection is explicitly requested. The optional `gh projects` extension is not a runtime dependency.

## Install

```bash
./scripts/install.sh
codex plugin add project-truss@personal --json
```

Start a fresh Codex session after installation.

## Use

Invoke `$project-truss:setup` once per repository, then `$project-truss:start` to begin or resume any Matt-first engineering work. Start grills when scope is unclear, invokes the relevant Matt disciplines, routes the Truss stages, and continues through verified closeout. The other four Truss skills are also callable when you intentionally enter a known stage; each returns control to Start.

```text
Use $project-truss:setup to configure this repository.
Use $project-truss:start to own this outcome through verified merge and closeout.
```

The installed skills are `setup`, `start`, `shape`, `resolve`, `close`, and `advanced-user-input`; Start is the normal beginning, not the only entrypoint.

## Develop and release

```bash
./scripts/validate.sh
./scripts/prepare-release.sh -Version 2.0.0 -CheckOnly
./scripts/sync-live.sh --validate
codex plugin add project-truss@personal --json
./scripts/get-agent-plugin-version.sh -Banner -RequireCurrent
```

Project Truss 2.0 is a clean cutover with no `deliver` alias or v1 issue parser. License: MIT.
