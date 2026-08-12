# Scientific benchmark and evidence protocol

This protocol is repository-agnostic. Target repositories own their equations, datasets, cases, commands, and tolerances; Project Truss owns the grammar that makes their scientific claims reviewable and resumable.

## Benchmark case

Validate with `-Action ValidateBenchmark`. Schema version 1 requires:

- `claim_id`, `title`, and `claim.statement`;
- `claim.type`: `independent_reference_value`, `analytical_identity`, `limiting_case`, `derivative_verification`, `solver_residual_certificate`, `metamorphic_relation`, `manufactured_solution`, `convergence_study`, `literature_reproduction`, `experimental_validation`, or `parameter_regression_validation`;
- source class and structured locator;
- oracle class plus an independence rationale;
- explicit inputs;
- one or more comparisons with quantity, metric, nonnegative finite `atol`/`rtol`, and tolerance basis;
- certificates, failure meaning, repository revision, exact command, and environment.

Oracle classes are `analytic`, `high_precision_derivation`, `independent_implementation`, `primary_literature`, `experimental`, `locked_publication_artifact`, `locked_validated_release`, and `change_detection_only`. Locked artifacts can guard an approved release/publication. `change_detection_only` cannot be claimed as independent scientific evidence.

```json
{
  "schema_version": 1,
  "claim_id": "C-1",
  "title": "Dilute limit recovers the ideal relation",
  "claim": {"type": "limiting_case", "statement": "As density tends to zero, Z tends to one."},
  "source": {"class": "analytic", "locator": {"document": "CONTEXT.md", "section": "Dilute limit"}},
  "oracle": {"class": "analytic", "independence_rationale": "The limit is derived independently of the implementation.", "claimed_independent": true},
  "inputs": {"temperature_K": 300.0, "density_mol_m3": [0.001, 0.0001]},
  "comparisons": [{"quantity": "Z", "metric": "absolute_error", "atol": 1e-8, "rtol": 1e-8, "tolerance_basis": "Truncation estimate plus double-precision roundoff."}],
  "certificates": ["monotone convergence toward 1"],
  "failure_meaning": "The implemented residual contribution does not vanish in the dilute limit.",
  "provenance": {"repository_revision": "FULL_SHA", "command": "python -m validation.dilute_limit", "environment": "locked environment hash"}
}
```

## Evidence packet

Validate with `-Action ValidateScientificEvidence`. Schema version 1 binds the packet to `github_issue`, an exact `issue_body_sha256`, `claim_id`, and a full experiment `repository_revision`, then records classification, source locators, assumptions, exact command/environment, limitations, and all six closeout dimensions. The validated tracked packet supplies a later `evidence_revision`; the experiment revision must be its ancestor. Model/input revisions are required once a model is selected. Numerical classifications also require raw-result paths, comparisons, certificates, and artifact SHA-256 receipts. Source-insufficient, source-conflict, model-mismatch, and not-attempted outcomes may leave numerical arrays and artifact receipts empty.

Classifications are `VERIFIED`, `FALSIFIED`, `PARTIALLY_VERIFIED`, `INCONCLUSIVE`, `SOURCE_INSUFFICIENT`, `SOURCE_CONFLICT`, `MODEL_VERSION_MISMATCH`, `NUMERICAL_FAILURE`, and `NOT_ATTEMPTED`.

Dimension states are deliberately separate:

- source: `verified`, `partial`, `conflicting`, `insufficient`;
- formulation: `verified`, `disputed`, `incomplete`, `not_applicable`;
- numerical verification: `verified`, `failed`, `inconclusive`, `not_applicable`;
- empirical validation: `validated`, `partial`, `outside_scope`, `failed`;
- reproducibility: `reproducible`, `environment_limited`, `incomplete`;
- implementation promotion: `promoted`, `experimental_only`, `not_applicable`.

Each dimension contains `state` and an evidence-link array. The packet also records a `scientific_review` object with the accountable GitHub reviewer, `passed`/`failed` verdict, and all six dimensions as its basis. The reviewer must post the matching receipt. Artifact paths are repository-relative and their SHA-256 digests must match at validation time. A `FALSIFIED` packet is complete when this same evidence contract is satisfied; negative results do not receive weaker provenance.

Path-backed validation requires the packet and artifacts at the evidence revision, then emits a compact `Project Truss scientific evidence receipt` containing the issue/body hash, claim, experiment/evidence revisions, packet path/hash, classification, review verdict, and dimension states. Post that returned receipt to the claimed GitHub issue before closure. Status uses only the latest accountable receipt and requires a passed review for scientific work to derive Done.
