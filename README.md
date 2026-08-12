# Project Truss

Project Truss is a profile-aware, GitHub-native harness around Matt Pocock's engineering techniques. It lets users call only the six Truss skills while Start selects the relevant Matt skills and carries an outcome through context, shaping, execution, evidence, merge or research closeout, and safe local cleanup.

Version 3.0 makes scientific computing and research a native execution profile rather than treating scientific repositories as ordinary software projects with extra tests.

| Profile | Primary unit of work | Default evidence |
|---|---|---|
| `application-development` | user-visible behavior or durable software contract | behavior tests, integration evidence, review |
| `scientific-computing` | falsifiable scientific claim | sources, formulation, independent benchmark or experiment, reproducible evidence packet |
| `general` | repository-defined | repository guidance |

Scientific work follows question → falsifiable claims → sources/data → formulation → experiment/benchmark → implementation when needed → scientific review → GitHub closeout. TDD is used only for an explicitly durable discrete software contract. A well-supported `FALSIFIED` result is successful scientific completion.

The canonical runtime contract is [docs/project-truss/README.md](docs/project-truss/README.md); the scientific protocol is [docs/project-truss/SCIENTIFIC.md](docs/project-truss/SCIENTIFIC.md).

## Requirements

- Codex with plugin support
- Git, Bash, Python 3, and authenticated `gh`
- Matt Pocock skills for the techniques Start may invoke
- native `gh project` support only when Project projection is requested

## Install and use

```bash
./scripts/install.sh
codex plugin add project-truss@personal --json
```

Start a fresh Codex session, run `$project-truss:setup` once per repository, then use `$project-truss:start`. The installed skills are `setup`, `start`, `shape`, `resolve`, `close`, and `advanced-user-input`; direct stage calls return to Start.

## Develop and release

```bash
./scripts/validate.sh
./scripts/prepare-release.sh -Version 3.0.0 -CheckOnly
./scripts/sync-live.sh --validate
codex plugin add project-truss@personal --json
./scripts/get-agent-plugin-version.sh -Banner -RequireCurrent
```

Project Truss 3.0 is a clean contract cutover with no v2 parser shim. License: MIT.
