---
name: close
description: Use after implementation or a pull request to review profile-specific evidence, merge or close the outcome, retire local state safely, and return to Start.
---

# Project Truss Close

Apply `docs/project-truss/contract.yml`. Close judges evidence and retires only the current outcome. CI/status checks and command-line transcript artifacts are optional context, not independent hard gates.

## Review

For published code, invoke Matt `code-review` against the recorded implementation base: Standards once over the shared diff and Spec once per selected issue. Resolve actionable findings.

Scientific work adds a separate Science review:

- source: provenance, authority, model/version match, units, and conventions;
- formulation: equations, assumptions, domain, and correspondence to the claim;
- numerical verification: oracle independence, tolerances, convergence/stability, residuals, and failure interpretation;
- empirical validation: only when relevant and available;
- reproducibility: exact revisions, command, environment, raw results, and artifact hashes;
- implementation promotion: production, experimental-only, or not applicable.

Record an evidence packet with one classification: `VERIFIED`, `FALSIFIED`, `PARTIALLY_VERIFIED`, `INCONCLUSIVE`, `SOURCE_INSUFFICIENT`, `SOURCE_CONFLICT`, `MODEL_VERSION_MISMATCH`, `NUMERICAL_FAILURE`, or `NOT_ATTEMPTED`. Validate it before Closeout:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action ValidateScientificEvidence -RepoRoot . \
  -ScientificEvidencePath PATH
```

A valid `FALSIFIED` packet is successful scientific completion. Do not relabel it as a workflow failure. Missing, contradictory, or unreproducible evidence remains a truthful scientific blocker.

Use a tracked repository-relative `ScientificEvidencePath`, post the validation action's exact returned scientific evidence receipt to the claimed issue, and re-read it before closure. The receipt binds the GitHub issue and body hash, experiment/evidence revisions, packet path/hash, classification, accountable passed review, and six dimension states; checked boxes, failed reviews, stale packets, and later claim edits never derive scientific Done.

## Close and merge

Run profile-selected verification. Governed code resolutions require matching receipts, checked issue criteria, the recorded PR/head, clear review state, healthy integration, clean source state, and—when scientific—a valid packet plus passed Science review. Optional checks do not gate merge. A scientific investigation with no code change may close directly from its evidence when its issue contract permits; do not fabricate a PR.

Merge the guarded head with authority, re-read GitHub, close selected issues from verified evidence, and post at most one concise closeout receipt. Project projection membership remains advisory unless explicitly required.

## Synchronize and retire

After GitHub confirms the PR merged and remote head deleted, run:

```bash
"$PROJECT_TRUSS_ROOT/scripts/project-truss.sh" -Action Cleanup -RepoRoot . -Repository OWNER/REPO \
  -CleanupJson '{"pull_request":123,"branch":"codex/issue-123","cleanup_authorized":true}'
```

Cleanup fetches/prunes, safely fast-forwards the discovered canonical default branch, and removes only the clean outcome worktree/branch. Current, protected, active, dirty, diverged, manually deleted, non-GitHub, mismatched, or unverified branches remain with a reason. Squash/rebase force-deletion requires exact merged-PR head proof. Without cleanup authority, synchronize and report `skipped_not_authorized`; never use an unguarded deletion loop.

Roll up a root only after all required children are terminal; a hierarchy is optional. Return to Start after review, retry, merge, Cleanup, or roll-up. Only truthful closeout is terminal.
