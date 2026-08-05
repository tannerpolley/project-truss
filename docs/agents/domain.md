# Domain documentation

This is a single-context repository.

- Read the root `CONTEXT.md` before shaping or implementation. It is the repository's shared glossary and conceptual language, not a scratchpad, implementation spec, or lifecycle ledger.
- When a term is missing, fuzzy, or conflicting, Start invokes Matt's `domain-modeling` and `grilling` disciplines and updates the glossary inline.
- Keep durable architecture decisions under `docs/adr/`.
- Add an ADR only for a surprising, hard-to-reverse trade-off or a decision that changes an ownership boundary, authoritative source, public contract, or irreversible migration.
- Keep useful primary-source research in canonical product documentation when it affects behavior.
- Prototypes live on throwaway branches and leave only a linked verdict in the relevant issue or ADR.
