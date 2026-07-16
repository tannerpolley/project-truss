# Project Truss Method Cards

Load one card only when its trigger matches current evidence. Cards improve reasoning; they do not own lifecycle state or form a required sequence.

## Adversarial clarification

**Trigger:** A consequential request is underspecified, contradictory, or hides a product choice.

**Questions:** What observable outcome matters? Which assumption would most change the solution? What must not happen? Who owns the unresolved tradeoff?

**Stop condition:** One implementable interpretation remains, or a genuinely material decision must go to the user.

**Output:** A compact outcome statement, explicit non-goals, and the smallest unresolved decision.

## Domain language and invariants

**Trigger:** Ambiguous terminology or domain rules could let a locally plausible implementation be globally wrong.

**Questions:** Which words have precise meanings here? What quantities, states, units, conservation rules, or business constraints must remain true? Where is the model valid?

**Stop condition:** Terms map to repository concepts and acceptance can be expressed as domain invariants.

**Output:** A short glossary plus measurable invariants and validity bounds.

## Codebase wayfinding

**Trigger:** The change crosses unfamiliar code or ownership is unclear.

**Questions:** Where does input enter? Which module owns the decision? What downstream consumers observe it? Which tests protect the behavior family?

**Stop condition:** One narrow edit path and its verification surface are identified.

**Output:** A source-to-consumer map with likely edit points and risks.

## Causal diagnosis

**Trigger:** A defect, failed check, or inconsistent state lacks a demonstrated cause.

**Questions:** What is the earliest divergence from expected behavior? Which observation distinguishes competing causes? Can the failure be reproduced at the owning boundary?

**Stop condition:** Evidence selects one cause and predicts a focused fix.

**Output:** Reproduction, causal chain, rejected alternatives, and a minimal repair hypothesis.

## Architecture pressure test

**Trigger:** A proposed abstraction, service, workflow layer, or persistent state could increase long-term coordination cost.

**Questions:** Which capability owns this? Can current native state answer it? How many writers and synchronization edges appear? What deletion becomes possible?

**Stop condition:** The proposal has one owner, justified boundaries, and less total complexity than the alternatives.

**Output:** Keep/simplify/delete decision with coupling and migration consequences.

## Ruthless triage

**Trigger:** Scope, tests, artifacts, or requested features exceed the evidence needed for the outcome.

**Questions:** Which item changes user-visible utility or protects a real failure? What is duplicated, speculative, generated, or historical? What can be deferred without weakening truth?

**Stop condition:** Every retained item maps to outcome value, authority, ordering, evidence, or safety.

**Output:** A ranked keep/delete/defer list with one-line justification.

## Independently verifiable decomposition

**Trigger:** Several deliverables can progress separately but must converge into one outcome.

**Questions:** Can each unit merge and prove value independently? What native dependency orders them? Which integration health belongs only at the parent or milestone?

**Stop condition:** Leaves are independently executable, dependencies are minimal, and parent closeout is measurable.

**Output:** Leaf outcomes, dependency edges, ownership boundaries, and roll-up acceptance.

## Influence and attribution

These independently written method cards were informed by engineering patterns in mattpocock/skills (MIT), audited at commit e9fcdf95b402d360f90f1db8d776d5dd450f9234. Project Truss does not copy or require that repository at runtime.
