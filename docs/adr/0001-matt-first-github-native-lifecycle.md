# ADR 0001: Matt-first, GitHub-native lifecycle

Status: Accepted

## Context

Project Truss previously coupled its governed lifecycle to a provider-specific planning workflow and a six-heading issue format. That duplicated engineering method, made temporary planning artifacts part of lifecycle policy, and prevented one pull request from truthfully resolving an explicitly selected group of related leaves.

## Decision

Project Truss 2.0 delegates engineering technique to available Matt Pocock methods and owns only durable coordination. GitHub issues and native relationships, Git, pull requests, CI, reviews, and current worktrees are authoritative.

Governed roots and leaves use strict Matt-shaped v2 contracts. Resolve selects an explicit singleton or multi-leaf resolution set whose members share one owner, implementation base, worktree, branch, canonical receipt, and pull request. Full-set preflight and post-write verification fail closed because GitHub cannot mutate several issues transactionally.

Labels, milestones, and optional GitHub Project memberships are descriptive projections. Project Truss uses native `gh project` commands for an explicitly selected Project, but Project fields never derive lifecycle state.

The 2.0 cutover removes the Deliver skill and v1 parser instead of preserving aliases or compatibility shims.

## Consequences

- Ordinary coding remains direct; governed work stops when required Matt capabilities are absent.
- Existing unclaimed v1 issues must be reshaped before resolution.
- Set closeout requires matching receipts, one reviewed and verified merged pull request, checked acceptance, healthy integration, and clean source state.
- GitHub and Git history remain the only durable lifecycle record.
