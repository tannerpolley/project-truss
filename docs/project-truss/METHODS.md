# Project Truss Matt Method Routing

Project Truss is the user-facing facade. Users invoke `project-truss:setup` once per repository and `project-truss:start` for ongoing work; Truss routes its internal stages and Matt Pocock engineering methods. Project Truss owns GitHub-native coordination while Matt methods own shaping and implementation technique.

## Invocation modes

| Mode | Meaning |
|---|---|
| `invocable` | An installed model-invocable Matt skill is called when its trigger matches. |
| `facaded` | Project Truss adopts a command-only Matt contract and produces the equivalent repository result. |
| `missing` | A triggered required method is unavailable, so governed work stops with `method_capability_missing`. |
| `not_triggered` | The method is known but irrelevant to the current evidence. |

`setup-matt-pocock-skills`, `grill-with-docs`, and Wayfinder are facaded contracts. Setup writes the Matt-compatible repository structure. Wayfinder handles decision work that exceeds one context.

## Required shaping method

Matt's current `grill-with-docs` is the engineering wrapper around `grilling` plus `domain-modeling`. New governed outcomes and material rescope require that composition: one decision question at a time, at least one answer, repository facts inspected directly, and explicit confirmation before Shape. Domain terms and qualifying ADRs are recorded as they crystallize.

Resume an unchanged published issue without repeating grilling.

## Implementation methods

| Trigger | Method | Durable result |
|---|---|---|
| Stable behavior can be specified at an approved public seam | `tdd` | Behavior-level regression tests |
| A defect or failed check lacks a demonstrated cause | `diagnosing-bugs` | Reproduction and causal repair |
| A niche claim needs primary-source evidence | `research` | Canonical research note when useful |
| Domain language or invariants are ambiguous | `domain-modeling` | `CONTEXT.md` or an ADR |
| A design question needs executable evidence | `prototype` | Throwaway branch plus linked verdict |
| Git reports an active merge or rebase conflict | `resolving-merge-conflicts` | Verified conflict resolution |
| A shared diff is ready for handoff | `code-review` | Standards report plus per-ticket Spec reports |
| Governed code is implemented | `minimize-code-surface`, `cutthroat-code-cleanup` | One minimal canonical implementation |
| Scientific-computing code changes | `scientific-coding-and-testing` | Domain invariants, justified tolerances, and scientific verification |

Command-oriented Matt workflows such as setup and Wayfinder may be unavailable for model invocation. Truss reports them as `facaded`; it must not claim to have invoked a skill that is absent.

## Capability failure

Before governed work, `start` verifies repository setup and required methods against the actual available skill list. Plan infers shaping, quality, and profile methods; callers list only extra task-specific requirements. Missing setup routes to `project-truss:setup`. A triggered method that is neither invocable nor facaded produces `method_capability_missing`.

Direct work remains available. Governed work stops until the method is installed, configured, or the outcome is explicitly reshaped so that method is no longer required.

## Canonical evidence

Keep `CONTEXT.md`, ADRs, and useful research notes in repository-defined locations. Keep prototypes on throwaway branches with a linked verdict. GitHub issues hold the root spec and leaf tickets. Do not create local lifecycle mirrors or planning artifacts.

Wayfinder maps and their `## Question` tickets are decision artifacts, not Project Truss execution issues. Shape may cite them as source context, but creates fresh root and leaf contracts and never derives lifecycle state from Wayfinder metadata.
