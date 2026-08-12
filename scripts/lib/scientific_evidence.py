"""Validation for Project Truss scientific benchmarks and evidence packets."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping


CLAIM_FAMILIES = (
    "independent_reference_value", "analytical_identity", "limiting_case",
    "derivative_verification", "solver_residual_certificate", "metamorphic_relation",
    "manufactured_solution", "convergence_study", "literature_reproduction",
    "experimental_validation", "parameter_regression_validation",
)
ORACLE_CLASSES = (
    "analytic", "high_precision_derivation", "independent_implementation",
    "primary_literature", "experimental", "locked_publication_artifact",
    "locked_validated_release", "change_detection_only",
)
INDEPENDENT_ORACLES = {
    "analytic", "high_precision_derivation", "independent_implementation",
    "primary_literature", "experimental",
}
RESULT_CLASSIFICATIONS = (
    "VERIFIED", "FALSIFIED", "PARTIALLY_VERIFIED", "INCONCLUSIVE",
    "SOURCE_INSUFFICIENT", "SOURCE_CONFLICT", "MODEL_VERSION_MISMATCH",
    "NUMERICAL_FAILURE", "NOT_ATTEMPTED",
)
DIMENSION_STATES = {
    "source": {"verified", "partial", "conflicting", "insufficient"},
    "formulation": {"verified", "disputed", "incomplete", "not_applicable"},
    "numerical_verification": {"verified", "failed", "inconclusive", "not_applicable"},
    "empirical_validation": {"validated", "partial", "outside_scope", "failed"},
    "reproducibility": {"reproducible", "environment_limited", "incomplete"},
    "implementation_promotion": {"promoted", "experimental_only", "not_applicable"},
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REVISION = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_RECEIPT_PREFIX = "Project Truss scientific evidence receipt: "


def issue_body_sha256(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()


@dataclass(frozen=True)
class ScientificValidation:
    ok: bool
    findings: tuple[str, ...]
    evidence: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "findings": list(self.findings), "evidence": dict(self.evidence)}

    def receipt(self) -> str:
        packet_path = _text(self.evidence.get("packet_path"))
        if not self.ok or not packet_path:
            raise ValueError("a valid path-backed evidence packet is required for a receipt")
        payload = {
            key: self.evidence[key]
            for key in (
            "github_issue", "issue_body_sha256", "claim_id", "classification",
            "repository_revision", "evidence_revision", "scientific_review",
            "packet_sha256", "dimensions",
            )
        }
        payload["packet_path"] = packet_path
        return _RECEIPT_PREFIX + json.dumps(payload, sort_keys=True, separators=(",", ":"))


def parse_scientific_receipt(body: str) -> Mapping[str, Any] | None:
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith(_RECEIPT_PREFIX)]
    if not lines:
        return None
    if len(lines) != 1:
        raise ValueError("scientific comment must contain one evidence receipt")
    value = json.loads(lines[0][len(_RECEIPT_PREFIX):])
    required = {
        "github_issue", "issue_body_sha256", "claim_id", "classification",
        "repository_revision", "evidence_revision", "scientific_review",
        "packet_sha256", "dimensions", "packet_path",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("scientific evidence receipt has an invalid shape")
    if (
        type(value["github_issue"]) is not int or value["github_issue"] < 1
        or _SHA256.fullmatch(_text(value["issue_body_sha256"])) is None
        or not _text(value["claim_id"])
        or _text(value["classification"]).upper() not in RESULT_CLASSIFICATIONS
        or _REVISION.fullmatch(_text(value["repository_revision"])) is None
        or _REVISION.fullmatch(_text(value["evidence_revision"])) is None
        or _SHA256.fullmatch(_text(value["packet_sha256"])) is None
        or not _text(value["packet_path"])
        or Path(value["packet_path"]).is_absolute()
        or ".." in Path(value["packet_path"]).parts
        or set(_mapping(value["dimensions"])) != set(DIMENSION_STATES)
        or any(state not in DIMENSION_STATES[name] for name, state in value["dimensions"].items())
        or set(_mapping(value["scientific_review"])) != {"reviewer", "verdict", "basis"}
        or not _text(value["scientific_review"].get("reviewer"))
        or value["scientific_review"].get("verdict") not in {"passed", "failed"}
        or not isinstance(value["scientific_review"].get("basis"), list)
        or set(value["scientific_review"]["basis"]) != set(DIMENSION_STATES)
    ):
        raise ValueError("scientific evidence receipt contains invalid evidence")
    return value


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value: Any, *, allow_empty: bool = False) -> tuple[str, ...] | None:
    if not isinstance(value, list) or any(not _text(item) for item in value):
        return None
    if not allow_empty and not value:
        return None
    normalized = tuple(_text(item) for item in value)
    return normalized if len(normalized) == len(set(normalized)) else None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _validate_comparisons(value: Any, findings: list[str], *, required: bool = True) -> int:
    if not isinstance(value, list) or not value:
        if required:
            findings.append("comparisons_required")
        return 0
    for index, raw in enumerate(value):
        item = _mapping(raw)
        prefix = f"comparison_{index}"
        if not all(_text(item.get(name)) for name in ("quantity", "metric", "tolerance_basis")):
            findings.append(f"{prefix}_definition_invalid")
        atol, rtol = item.get("atol"), item.get("rtol")
        if any(type(number) not in {int, float} or not math.isfinite(number) or number < 0 for number in (atol, rtol)) or not (atol or rtol):
            findings.append(f"{prefix}_tolerance_invalid")
    return len(value)


def validate_benchmark_case(data: Any) -> ScientificValidation:
    findings: list[str] = []
    case = _mapping(data)
    if case.get("schema_version") != 1:
        findings.append("schema_version_invalid")
    claim, source, oracle, provenance = (
        _mapping(case.get(name)) for name in ("claim", "source", "oracle", "provenance")
    )
    claim_type = _text(claim.get("type"))
    if not _text(case.get("claim_id")) or not _text(case.get("title")) or not _text(claim.get("statement")):
        findings.append("claim_definition_invalid")
    if claim_type not in CLAIM_FAMILIES:
        findings.append("claim_family_invalid")
    if not _text(source.get("class")) or not _mapping(source.get("locator")):
        findings.append("source_locator_invalid")
    oracle_class = _text(oracle.get("class"))
    if oracle_class not in ORACLE_CLASSES or not _text(oracle.get("independence_rationale")):
        findings.append("oracle_definition_invalid")
    if oracle_class == "change_detection_only" and oracle.get("claimed_independent") is True:
        findings.append("change_detection_claimed_independent")
    if not isinstance(case.get("inputs"), Mapping):
        findings.append("inputs_invalid")
    comparison_count = _validate_comparisons(case.get("comparisons"), findings)
    if _strings(case.get("certificates")) is None:
        findings.append("certificates_required")
    if not _text(case.get("failure_meaning")):
        findings.append("failure_meaning_required")
    if (
        not all(_text(provenance.get(name)) for name in ("repository_revision", "command", "environment"))
        or _REVISION.fullmatch(_text(provenance.get("repository_revision"))) is None
    ):
        findings.append("provenance_incomplete")
    strength = (
        "independent" if oracle_class in INDEPENDENT_ORACLES
        else "locked" if oracle_class.startswith("locked_")
        else "change_detection" if oracle_class == "change_detection_only"
        else "invalid"
    )
    evidence = {
        "claim_id": _text(case.get("claim_id")), "claim_family": claim_type,
        "oracle_class": oracle_class, "oracle_strength": strength,
        "comparison_count": comparison_count,
    }
    return ScientificValidation(not findings, tuple(findings), evidence)


def _validate_dimensions(value: Any, findings: list[str]) -> dict[str, str]:
    dimensions = _mapping(value)
    states: dict[str, str] = {}
    if set(dimensions) != set(DIMENSION_STATES):
        findings.append("closeout_dimensions_incomplete")
    for name, allowed in DIMENSION_STATES.items():
        item = _mapping(dimensions.get(name))
        state = _text(item.get("state"))
        states[name] = state
        if state not in allowed:
            findings.append(f"{name}_state_invalid")
        if _strings(item.get("evidence"), allow_empty=state in {"outside_scope", "not_applicable"}) is None:
            findings.append(f"{name}_evidence_invalid")
    return states


def _validate_artifacts(
    value: Any, root: Path | None, findings: list[str], *, required: bool = True,
    revision: str = "",
) -> int:
    artifacts = _mapping(value)
    if not artifacts:
        if required:
            findings.append("artifact_hashes_required")
        return 0
    for raw_path, raw_digest in artifacts.items():
        path, digest = _text(raw_path), _text(raw_digest).casefold()
        if not path or Path(path).is_absolute() or ".." in Path(path).parts or _SHA256.fullmatch(digest) is None:
            findings.append("artifact_receipt_invalid")
            continue
        if root is None:
            continue
        content = _git_blob(root, revision, path) if revision else (root / path).read_bytes() if (root / path).is_file() else None
        if content is None:
            findings.append("evidence_artifact_missing")
        elif hashlib.sha256(content).hexdigest() != digest:
            findings.append("evidence_artifact_mismatch")
    return len(artifacts)


def _git_blob(root: Path, revision: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"], cwd=root,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15,
    )
    return result.stdout if result.returncode == 0 else None


def validate_evidence_packet(
    data: Any, root: Path | None = None, *, packet_path: str = "",
    packet_key: str = "",
    expected_issue: int | None = None, expected_issue_body_sha256: str = "",
    expected_revision: str = "",
) -> ScientificValidation:
    findings: list[str] = []
    packet = _mapping(data)
    if packet.get("schema_version") != 1:
        findings.append("schema_version_invalid")
    github_issue = packet.get("github_issue")
    issue_body_sha256 = _text(packet.get("issue_body_sha256"))
    claim_id, classification = _text(packet.get("claim_id")), _text(packet.get("classification")).upper()
    if type(github_issue) is not int or github_issue < 1 or expected_issue and github_issue != expected_issue:
        findings.append("github_issue_invalid")
    if _SHA256.fullmatch(issue_body_sha256) is None or expected_issue_body_sha256 and issue_body_sha256 != expected_issue_body_sha256:
        findings.append("issue_body_sha256_invalid")
    if not claim_id:
        findings.append("claim_id_required")
    if classification not in RESULT_CLASSIFICATIONS:
        findings.append("classification_invalid")
    if _strings(packet.get("source_locators")) is None:
        findings.append("source_locators_required")
    if _strings(packet.get("assumptions"), allow_empty=True) is None:
        findings.append("assumptions_invalid")
    for name in ("repository_revision", "command", "environment"):
        if not _text(packet.get(name)):
            findings.append(f"{name}_required")
    if _REVISION.fullmatch(_text(packet.get("repository_revision"))) is None:
        findings.append("repository_revision_invalid")
    if expected_revision and root:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", _text(packet.get("repository_revision")), expected_revision],
            cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
        )
        if ancestor.returncode:
            findings.append("repository_revision_mismatch")
    numerical_required = classification not in {
        "SOURCE_INSUFFICIENT", "SOURCE_CONFLICT", "MODEL_VERSION_MISMATCH", "NOT_ATTEMPTED",
    }
    if classification not in {"SOURCE_INSUFFICIENT", "SOURCE_CONFLICT", "NOT_ATTEMPTED"}:
        for name in ("model_revision", "input_revision"):
            if not _text(packet.get(name)):
                findings.append(f"{name}_required")
    raw_results = _strings(packet.get("raw_results"), allow_empty=not numerical_required)
    if raw_results is None:
        findings.append("raw_results_required")
    comparison_count = _validate_comparisons(packet.get("comparisons"), findings, required=numerical_required)
    if _strings(packet.get("certificates"), allow_empty=not numerical_required) is None:
        findings.append("certificates_required")
    if _strings(packet.get("limitations"), allow_empty=True) is None:
        findings.append("limitations_invalid")
    states = _validate_dimensions(packet.get("dimensions"), findings)
    review = _mapping(packet.get("scientific_review"))
    if (
        set(review) != {"reviewer", "verdict", "basis"}
        or not _text(review.get("reviewer"))
        or review.get("verdict") not in {"passed", "failed"}
        or _strings(review.get("basis")) is None
        or set(review.get("basis", ())) != set(DIMENSION_STATES)
    ):
        findings.append("scientific_review_invalid")
    artifact_count = _validate_artifacts(
        packet.get("artifact_hashes"), root, findings,
        required=numerical_required, revision=expected_revision,
    )
    if raw_results and not set(raw_results) <= set(_mapping(packet.get("artifact_hashes"))):
        findings.append("raw_result_hash_missing")
    required_states = {
        "SOURCE_INSUFFICIENT": {"source": "insufficient"},
        "SOURCE_CONFLICT": {"source": "conflicting"},
        "NUMERICAL_FAILURE": {"numerical_verification": "failed"},
        "INCONCLUSIVE": {"numerical_verification": "inconclusive"},
        "NOT_ATTEMPTED": {"numerical_verification": "not_applicable"},
    }.get(classification, {})
    decisive = classification in {"VERIFIED", "FALSIFIED"}
    if (
        any(states.get(name) != state for name, state in required_states.items())
        or decisive and (
            states.get("source") != "verified"
            or states.get("formulation") not in {"verified", "not_applicable"}
            or states.get("numerical_verification") != "verified"
            or states.get("reproducibility") != "reproducible"
        )
    ):
        findings.append("classification_dimension_conflict")
    packet_sha256 = hashlib.sha256(
        json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    if expected_revision and packet_path and root:
        tracked_packet = _git_blob(root, expected_revision, packet_path)
        if tracked_packet is None:
            findings.append("evidence_packet_untracked")
        else:
            try:
                tracked = json.loads(tracked_packet)
                if packet_key:
                    tracked = _mapping(tracked.get("issues", tracked)).get(packet_key)
                tracked_hash = hashlib.sha256(json.dumps(tracked, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            except (UnicodeDecodeError, json.JSONDecodeError):
                tracked_hash = ""
            if tracked_hash != packet_sha256:
                findings.append("evidence_packet_revision_mismatch")
    evidence = {
        "github_issue": github_issue, "issue_body_sha256": issue_body_sha256,
        "claim_id": claim_id, "classification": classification,
        "repository_revision": _text(packet.get("repository_revision")),
        "evidence_revision": expected_revision or _text(packet.get("repository_revision")),
        "scientific_review": dict(review),
        "comparison_count": comparison_count, "artifact_count": artifact_count,
        "dimensions": states,
        "packet_sha256": packet_sha256, "packet_path": packet_path,
        "negative_result_is_complete": classification == "FALSIFIED" and not findings,
    }
    return ScientificValidation(not findings, tuple(dict.fromkeys(findings)), evidence)
