---
name: close
description: Use when Project Truss must verify, merge, roll up, and retire a governed outcome from fresh repository and GitHub evidence.
---

# Project Truss Close

Apply `docs/project-truss/contract.yml`. Completion is derived from current GitHub, Git, CI, repository health, and working-artifact state.

## Prove the leaf

Run repository-profile-selected verification and upstream `superpowers:verification-before-completion`. Re-read the issue, acceptance checkboxes, assignee, dependencies, comments, closing pull request, review state, check runs, and current head. Do not merge or close while that evidence is incomplete.

If merge or parent-close authority is absent, ask once through `advanced-user-input`. For a code leaf, use upstream `superpowers:finishing-a-development-branch`, guard the selected head, merge, and then re-read live state. For a parent, close it only after every required child and integrated health check pass.

Before the authorized transition, retire completed Superpowers working files under `docs/superpowers/specs/` and `docs/superpowers/plans/`. Delete change-local material once Git and GitHub preserve the outcome; move any lasting insight to the repository's own canonical documentation location. Keep files still needed by an active child in that child's isolated branch or worktree, not in the final integrated tree.

After the authorized transition, invoke `scripts/project-truss.sh -Action Closeout` with final health bound to the closing pull-request head and `source_clean` from a fresh status check. Closeout automatically reports any remaining Superpowers working-file paths and treats them as unhealthy integration. This current-session health is cooperative evidence, not host cryptographic attestation; do not claim otherwise. Show concise evidence and findings. A code leaf requires exactly one owner, one merged closing pull request, completed successful checks, no unresolved review decision, checked acceptance, healthy integration, clean source state, retired working artifacts, and no contradiction. Never promote an intermediate artifact or self-reported success to completion.

## Roll up and retire

Close a parent only when every required child derives Done. Close a milestone or outcome only after descendants and final integrated repository health are clean. Mark acceptance from evidence, post at most one concise verified closeout receipt, and remove only outcome-owned branches, worktrees, processes, caches, and temporary working artifacts.

Keep active artifacts needed by a remaining child. GitHub and Git history are the durable record. Stop on failed or pending checks, unchecked acceptance, incomplete descendants, unhealthy integration, stale head, unavailable provider truth, or conflicting state.
