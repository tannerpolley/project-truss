# Project Truss Plugin Repo

This repository is the canonical source for the Project Truss Codex plugin.

Repository Profile: application-development

## Rules

- Treat this repository as source and `~/.codex/plugins/project-truss` as the deployed source copy.
- Never edit deployed or plugin-cache files directly. Edit source, validate, commit, then use the supported sync and plugin commands.
- Prefer the smallest maintainable change. Delete displaced code, tests, generated output, and working artifacts in the same change.
- Tests protect behavior families, authority, dependency ordering, merge safety, and truthful closeout; do not add helper-level or coverage-driven bulk.
- Ordinary maintenance remains direct unless Project Truss is explicit or a hard continuity trigger exists.
- Governed lifecycle truth comes from GitHub, Git, CI, and current worktrees. Do not add a second persistent state store.
- Keep durable issue comments to claim/start, blocker or decision, handoff, and verified closeout.
- Use hidden Codex worktrees for issue implementation. After merge, restore canonical local `main` with no feature branch or linked worktree.
- Product documentation belongs under `docs/project-truss/`. Superpowers specs and plans are temporary shaping inputs: retain them through GitHub issue creation and verification, then delete them before Ready claim, delivery, or an implementation branch/worktree. Retain them on failed verification, promote only lasting insight to canonical documentation, and use the recorded implementation-base commit to prove they never enter implementation history.
- Repository profiles select verification behavior. Scientific repositories use domain invariants and engineering tolerances; application repositories use meaningful behavior, integration, and product acceptance.

## Required Post-Revision Loop

Changes under `.codex-plugin/`, `skills/`, `assets/`, `scripts/`, or runtime-included `docs/project-truss/` paths change the installable surface. Before reporting such a revision complete:

1. Run `./scripts/validate.sh`.
2. Commit the intended source changes. If commit authority is absent, request it and stop before deployment.
3. Run `./scripts/sync-live.sh --validate`.
4. Run `codex plugin add project-truss@personal --json`.
5. Run `./scripts/get-agent-plugin-version.sh -Banner -RequireCurrent`.
6. Run `bash "$HOME/.codex/hooks/codex-cleanup.sh" --repo-root .`.
7. Confirm `git status --short --branch` shows the expected branch state.
8. Tell the user to start a fresh Codex session.

Report every skipped or failed gate. Validation or sync alone does not complete an installable revision.

## Validation

```bash
./scripts/validate.sh
```

Before updating the live source copy:

```bash
./scripts/sync-live.sh --validate
```
