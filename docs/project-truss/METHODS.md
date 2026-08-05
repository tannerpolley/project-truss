# Project Truss Matt Method Routing

Project Truss coordinates durable GitHub outcomes and directly invokes Matt Pocock engineering disciplines. Run `project-truss:setup` once per repository, then use `project-truss:start` for normal Matt-first work. The other four lifecycle skills remain callable for intentional stage entry and return to Start. Project Truss owns GitHub-native coordination while Matt methods own shaping and implementation technique.

## Invocation modes

| Mode | Meaning |
|---|---|
| `invocable` | An installed model-invocable Matt skill is called when its trigger matches. |
| `missing` | A triggered governed method is unavailable, so governed work stops with `method_capability_missing`; light work reports a degradation and continues. |
| `not_triggered` | The method is known but irrelevant to the current evidence. |

`setup-matt-pocock-skills`, `grill-with-docs`, and Wayfinder are user-invoked or native planning surfaces, not method routes silently chained by another user-invoked skill. Setup applies the repository configuration contract. Start directly invokes model-invocable `grilling` and `domain-modeling`; Wayfinder remains a native Truss planning artifact.

## Adaptive shaping

Matt's current `grill-with-docs` is the engineering wrapper around `grilling` plus `domain-modeling`. Start first reads the repository context glossary, records relevant terms, and routes missing or fuzzy vocabulary through that same composition: one decision question at a time, repository facts inspected directly, and explicit confirmation before Shape. Complete light requests with clear vocabulary skip the interview. Domain terms are written into `CONTEXT.md`; qualifying ADRs are recorded only for surprising, hard-to-reverse trade-offs.

Resume an unchanged published issue without repeating grilling.

## Implementation methods

| Trigger | Method | Durable result |
|---|---|---|
| Stable behavior can be specified at an approved public seam | `tdd` | Behavior-level regression tests |
| A defect or failed check lacks a demonstrated cause | `diagnosing-bugs` | Reproduction and causal repair |
| A niche claim needs primary-source evidence | `research` | Canonical research note when useful |
| Domain language or invariants are ambiguous | `domain-modeling` | `CONTEXT.md` or an ADR |
| A module boundary or interface needs deliberate design | `codebase-design` | A deep, named module boundary with a small public surface |
| A design question needs executable evidence | `prototype` | Throwaway branch plus linked verdict |
| Git reports an active merge or rebase conflict | `resolving-merge-conflicts` | Verified conflict resolution |
| A shared diff is ready for handoff | `code-review` | Standards report plus per-ticket Spec reports |
| High-risk or structural code is implemented | `minimize-code-surface`, `cutthroat-code-cleanup` | One minimal canonical implementation |
| A human must provision, enter secrets, use an unfamiliar dashboard, or perform a one-off migration/cutover | `wizard` | Staged bash wizard for the human; never run it end to end |
| Skills, `AGENTS.md`, `CLAUDE.md`, or other agent-facing docs change | `writing-for-agents` | Progressive, explicit, single-sourced agent instructions |
| Scientific-computing code changes | `scientific-coding-and-testing` | Domain invariants, justified tolerances, and scientific verification |

User-invoked Matt workflows such as repository setup and `grill-with-docs` may not be callable as model-invoked methods. Truss does not claim to have invoked them. It directly routes to the installed model-invocable disciplines that provide the required engineering behavior.

## Capability failure

Before governed work, `start` verifies repository setup and required methods against the actual available skill list. Plan infers shaping, quality, risk, and profile methods; callers list only extra task-specific requirements. Missing setup routes to `project-truss:setup`. A triggered governed method that is not invocable produces `method_capability_missing`; light work exposes the missing route without inventing a skip.

Direct and light work remain available. Governed work stops until the method is installed, configured, or the outcome is explicitly reshaped so that method is no longer required.

## Canonical evidence

Keep `CONTEXT.md`, ADRs, and useful research notes in repository-defined locations. Keep prototypes on throwaway branches with a linked verdict. GitHub issues hold root specs, standalone tickets, and leaves. Do not create local lifecycle mirrors or planning artifacts.

Wayfinder maps and their `## Question` tickets are decision artifacts, not Project Truss execution issues. Shape may cite them as source context, but creates fresh root and leaf contracts and never derives lifecycle state from Wayfinder metadata.
