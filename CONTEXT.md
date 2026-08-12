# Project Truss domain context

Project Truss is a profile-aware, GitHub-native harness around Matt Pocock techniques. It coordinates durable outcomes without replacing repository truth or creating a lifecycle database.

## Language

- **Repository profile:** `application-development`, `scientific-computing`, or `general`; the selected doctrine for shaping, execution, and evidence.
- **Context pass:** Start's read-and-confirm step over applicable context files and canonical terms.
- **Shared vocabulary:** project terms that carry one meaning across sources, issues, formulations, code, and reviews.
- **Truss harness:** the six user-facing skills that select profiles, invoke techniques, and maintain continuity.
- **Matt technique:** a focused method such as research, grilling, domain modeling, prototype, TDD, diagnosis, or code review invoked by Start when triggered.
- **Direct/light/governed:** no durable coordination, one standalone issue/PR, or coordinated work respectively.
- **Standalone issue:** a self-contained executable contract with no required parent.
- **Root/leaf:** optional decomposition for genuinely coordinated work.
- **Scientific question:** the bounded unknown motivating scientific work.
- **Falsifiable claim:** a statement paired with an observation that could show it false.
- **Benchmark case:** a durable claim-specific comparison with source, oracle class, inputs, justified tolerances, certificates, failure meaning, and provenance.
- **Oracle independence:** whether reference evidence is meaningfully independent of the implementation under test.
- **Evidence packet:** the reproducible record of sources, assumptions, revisions, command/environment, raw results, comparisons, certificates, limitations, artifact hashes, and closeout judgments.
- **Science review:** separate assessment of source, formulation, numerical verification, empirical validation, reproducibility, and implementation promotion.
- **Result classification:** the scientific outcome, including `VERIFIED`, `FALSIFIED`, partial/inconclusive/source/model/numerical statuses, or `NOT_ATTEMPTED`.
- **Resolution set:** one selected standalone issue/leaf or truly atomic group sharing one owner, synchronized base, attached worktree, branch, receipt, and PR when code changes.
- **Projection:** advisory label, milestone, or GitHub Project membership; never lifecycle state.
- **Canonical checkout / synchronized implementation base:** the live default checkout and exact remote-aligned commit captured after fetch/prune and fast-forward-only synchronization.
- **Outcome retirement:** authorized removal of only a verified merged outcome's clean local branch/worktree.

## Invariants

- GitHub, Git, reviews, integration, and worktrees are authoritative; optional checks, projections, benchmark files, and evidence artifacts are content or context, not lifecycle authority.
- Users can call only Project Truss skills; Start selects relevant Matt techniques and continues.
- Scientific work begins with a question and falsifiable claim, not implementation or generic TDD.
- TDD applies only to an explicitly durable discrete software contract.
- Change-detection snapshots are not independent scientific oracles.
- A valid `FALSIFIED` result is successful scientific completion.
- Every unfinished state has a next action; intermediate publication, implementation, PR, review, merge, and pre-cleanup are not terminal.
- Parent/leaf hierarchy and PRs are optional when the outcome does not need them.
- Partial external mutation fails closed; retirement never mutates unrelated or unverified state.
