# Project Truss Matt Method Routing

Project Truss owns GitHub-native coordination. Matt Pocock engineering skills own shaping and implementation technique. Route only when current evidence matches a method; availability is a capability, not something to assume.

## Required shaping method

New governed outcomes and material rescope require `grilling` to reach shared understanding. Add `domain-modeling` when language, invariants, ownership, or state transitions are unclear.

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

Command-oriented Matt workflows such as setup, grilling-with-docs, spec publication, ticket publication, and implement may be unavailable for model invocation. Truss adopts their contracts and outputs; it must not claim to have invoked a method that is absent.

## Capability failure

Before governed work, `start` verifies repository setup and required methods against the actual available skill list. A missing package, `docs/agents/` configuration, or required method produces `method_capability_missing`.

Direct work remains available. Governed work stops until the method is installed, configured, or the outcome is explicitly reshaped so that method is no longer required.

## Canonical evidence

Keep `CONTEXT.md`, ADRs, and useful research notes in repository-defined locations. Keep prototypes on throwaway branches with a linked verdict. GitHub issues hold the root spec and leaf tickets. Do not create local lifecycle mirrors or planning artifacts.
