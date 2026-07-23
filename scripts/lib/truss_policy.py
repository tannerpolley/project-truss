"""Pure Project Truss planning and current-state lifecycle policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any, ClassVar, Mapping

import yaml


SKILLS = ("start", "shape", "resolve", "close", "advanced-user-input")
HARD_TRIGGERS = (
    "explicit",
    "merge_or_publication",
    "release_or_milestone",
    "multiple_independent_units",
    "multi_agent_delegation",
    "exceeds_safe_context",
)
ROOT_ISSUE_SECTIONS = (
    "Problem Statement",
    "Solution",
    "User Stories",
    "Implementation Decisions",
    "Testing Decisions",
    "Out of Scope",
    "Further Notes",
)
LEAF_ISSUE_SECTIONS = (
    "Parent",
    "What to build",
    "Acceptance criteria",
    "Blocked by",
)
ADVISORY_LABELS = {"ready_for_agent": "agent-shaped"}
RECEIPTS = ("claim", "blocker_or_decision", "handoff", "verified_closeout")
BLOCKERS = (
    "authority_required",
    "decision_required",
    "github_capability_missing",
    "method_capability_missing",
    "contract_incomplete",
    "dependency_blocked",
    "claim_conflict",
    "verification_failed",
    "integration_unhealthy",
    "state_contradiction",
    "external_state_unavailable",
)
_CONTRACT_KEYS = {
    "version",
    "public_skill",
    "skills",
    "hard_triggers",
    "root_issue_sections",
    "leaf_issue_sections",
    "advisory_labels",
    "receipts",
    "blockers",
}


def _strict_mapping(data: Mapping[str, Any], fields: set[str], label: str) -> dict[str, Any]:
    unknown = sorted(set(data) - fields)
    if unknown:
        raise ValueError(f"unknown {label} field(s): {', '.join(unknown)}")
    return dict(data)


def _bool(data: Mapping[str, Any], name: str, default: bool = False) -> bool:
    value = data.get(name, default)
    if type(value) is not bool:
        raise ValueError(f"{name} must be boolean")
    return value


def _positive_int(data: Mapping[str, Any], name: str, default: int = 1) -> int:
    value = data.get(name, default)
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _strings(data: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = data.get(name, ())
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{name} must be an array of non-empty strings")
    normalized = tuple(item.strip() for item in value)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{name} must not contain duplicates")
    return normalized


@dataclass(frozen=True)
class WorkRequest:
    explicit: bool = False
    merge_or_publication: bool = False
    release_or_milestone: bool = False
    independent_units: int = 1
    delegated_owners: int = 1
    exceeds_safe_context: bool = False
    material_decision_missing: bool = False
    matt_configured: bool = False
    new_outcome: bool = False
    material_rescope: bool = False
    required_methods: tuple[str, ...] = ()
    available_methods: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkRequest":
        values = _strict_mapping(data, set(cls.__dataclass_fields__), "work request")
        return cls(
            explicit=_bool(values, "explicit"),
            merge_or_publication=_bool(values, "merge_or_publication"),
            release_or_milestone=_bool(values, "release_or_milestone"),
            independent_units=_positive_int(values, "independent_units"),
            delegated_owners=_positive_int(values, "delegated_owners"),
            exceeds_safe_context=_bool(values, "exceeds_safe_context"),
            material_decision_missing=_bool(values, "material_decision_missing"),
            matt_configured=_bool(values, "matt_configured"),
            new_outcome=_bool(values, "new_outcome"),
            material_rescope=_bool(values, "material_rescope"),
            required_methods=_strings(values, "required_methods"),
            available_methods=_strings(values, "available_methods"),
        )


@dataclass(frozen=True)
class TrussPlan:
    lane: str
    layers: tuple[str, ...]
    question_required: bool
    blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "layers": list(self.layers),
            "question_required": self.question_required,
            "blockers": list(self.blockers),
        }


def plan_work(request: WorkRequest) -> TrussPlan:
    governed = any(
        (
            request.explicit,
            request.merge_or_publication,
            request.release_or_milestone,
            request.independent_units > 1,
            request.delegated_owners > 1,
            request.exceeds_safe_context,
        )
    )
    if not governed:
        return TrussPlan("direct", (), False, ())
    layers = ["leaf", "pull_request"]
    if request.independent_units > 1:
        layers.insert(0, "parent")
    if request.release_or_milestone and request.independent_units > 1:
        layers.insert(0, "milestone")
    required = set(request.required_methods)
    if request.new_outcome or request.material_rescope:
        required.add("grilling")
    missing_method = not request.matt_configured or not required.issubset(
        request.available_methods
    )
    blockers = ("method_capability_missing",) if missing_method else ()
    return TrussPlan(
        "governed",
        tuple(layers),
        request.material_decision_missing,
        blockers,
    )


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    state: str
    url: str
    body: str = ""
    lifecycle_state: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Issue":
        return cls(
            number=int(data["number"]),
            title=str(data["title"]),
            state=str(data["state"]).upper(),
            url=str(data["url"]),
            body=str(data.get("body") or ""),
            lifecycle_state=str(data["lifecycle_state"]) if data.get("lifecycle_state") else None,
        )


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    url: str
    merged: bool
    merged_at: str | None
    head_sha: str
    checks_complete: bool
    checks_successful: bool
    review_decision: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PullRequest":
        return cls(
            number=int(data["number"]),
            state=str(data["state"]).upper(),
            url=str(data["url"]),
            merged=_bool(data, "merged"),
            merged_at=str(data["merged_at"]) if data.get("merged_at") else None,
            head_sha=str(data.get("head_sha") or ""),
            checks_complete=_bool(data, "checks_complete"),
            checks_successful=_bool(data, "checks_successful"),
            review_decision=str(data.get("review_decision") or ""),
        )


@dataclass(frozen=True)
class Comment:
    author: str
    body: str
    created_at: str
    url: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Comment":
        return cls(
            author=str(data.get("author") or ""),
            body=str(data.get("body") or ""),
            created_at=str(data.get("created_at") or ""),
            url=str(data.get("url") or ""),
        )


@dataclass(frozen=True)
class OutcomeSnapshot:
    authoritative: bool
    observed_at: str
    repository: str
    issue: Issue
    assignees: tuple[str, ...]
    children: tuple[Issue, ...]
    blocked_by: tuple[Issue, ...]
    blocking: tuple[Issue, ...]
    closing_prs: tuple[PullRequest, ...]
    comments: tuple[Comment, ...]
    source_urls: tuple[str, ...]
    provider_findings: tuple[str, ...] = ()
    parent: Issue | None = None
    milestone: Issue | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "OutcomeSnapshot":
        return cls(
            authoritative=_bool(data, "authoritative"),
            observed_at=str(data.get("observed_at") or ""),
            repository=str(data["repository"]),
            issue=Issue.from_mapping(data["issue"]),
            assignees=tuple(str(value) for value in data.get("assignees", [])),
            children=tuple(Issue.from_mapping(value) for value in data.get("children", [])),
            blocked_by=tuple(Issue.from_mapping(value) for value in data.get("blocked_by", [])),
            blocking=tuple(Issue.from_mapping(value) for value in data.get("blocking", [])),
            closing_prs=tuple(PullRequest.from_mapping(value) for value in data.get("closing_prs", [])),
            comments=tuple(Comment.from_mapping(value) for value in data.get("comments", [])),
            source_urls=tuple(str(value) for value in data.get("source_urls", [])),
            provider_findings=tuple(str(value) for value in data.get("provider_findings", [])),
            parent=Issue.from_mapping(data["parent"]) if data.get("parent") else None,
            milestone=Issue.from_mapping(data["milestone"]) if data.get("milestone") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in ("assignees", "children", "blocked_by", "blocking", "closing_prs", "comments", "source_urls", "provider_findings"):
            result[key] = list(result[key])
        return result


@dataclass(frozen=True)
class FinalHealth:
    verification_passed: bool
    integration_healthy: bool
    source_clean: bool
    head_sha: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "FinalHealth":
        values = _strict_mapping(data, set(cls.__dataclass_fields__), "final health")
        return cls(
            verification_passed=_bool(values, "verification_passed"),
            integration_healthy=_bool(values, "integration_healthy"),
            source_clean=_bool(values, "source_clean"),
            head_sha=str(values.get("head_sha") or ""),
        )


@dataclass(frozen=True)
class ResolutionReceipt:
    issues: tuple[int, ...]
    owner: str
    implementation_base: str
    branch: str
    worktree: str
    pull_request: int | None = None
    _COMMENT_PREFIX: ClassVar[str] = "Project Truss resolution receipt: "

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ResolutionReceipt":
        values = _strict_mapping(data, set(cls.__dataclass_fields__), "resolution receipt")
        raw_issues = values.get("issues")
        if not isinstance(raw_issues, list) or not raw_issues:
            raise ValueError("issues must be a non-empty array")
        issues = tuple(raw_issues)
        if any(type(number) is not int or number < 1 for number in issues):
            raise ValueError("issues must contain positive integers")
        if len(issues) != len(set(issues)):
            raise ValueError("issues must not contain duplicates")
        owner = str(values.get("owner") or "").strip()
        implementation_base = str(values.get("implementation_base") or "").strip()
        branch = str(values.get("branch") or "").strip()
        worktree = str(values.get("worktree") or "").strip()
        if not all((owner, branch, worktree)):
            raise ValueError("owner, branch, and worktree are required")
        if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", implementation_base) is None:
            raise ValueError("implementation_base must be a full Git commit hash")
        pull_request = values.get("pull_request")
        if pull_request is not None and (type(pull_request) is not int or pull_request < 1):
            raise ValueError("pull_request must be a positive integer")
        return cls(tuple(sorted(issues)), owner, implementation_base, branch, worktree, pull_request)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issues": list(self.issues),
            "owner": self.owner,
            "implementation_base": self.implementation_base,
            "branch": self.branch,
            "worktree": self.worktree,
            "pull_request": self.pull_request,
        }

    def comment(self) -> str:
        return self._COMMENT_PREFIX + json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_comment(cls, body: str) -> "ResolutionReceipt | None":
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        matches = [line for line in lines if line.startswith(cls._COMMENT_PREFIX)]
        if not matches:
            return None
        if len(matches) != 1:
            raise ValueError("resolution comment must contain exactly one receipt")
        payload = json.loads(matches[0][len(cls._COMMENT_PREFIX):])
        if not isinstance(payload, Mapping):
            raise ValueError("resolution receipt comment must contain a JSON object")
        return cls.from_mapping(payload)


@dataclass(frozen=True)
class ResolutionPlan:
    eligible: bool
    issues: tuple[int, ...]
    internal_dependencies: tuple[tuple[int, int], ...]
    external_blockers: tuple[int, ...]
    blockers: tuple[str, ...]
    receipt: ResolutionReceipt

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "issues": list(self.issues),
            "internal_dependencies": [
                {"blocked": blocked, "blocked_by": blocked_by}
                for blocked, blocked_by in self.internal_dependencies
            ],
            "external_blockers": list(self.external_blockers),
            "blockers": list(self.blockers),
            "receipt": self.receipt.to_dict(),
        }


def plan_resolution(
    snapshots: list[OutcomeSnapshot] | tuple[OutcomeSnapshot, ...],
    receipt: ResolutionReceipt,
    *,
    require_recorded: bool = False,
) -> ResolutionPlan:
    selected = set(receipt.issues)
    observed = {snapshot.issue.number: snapshot for snapshot in snapshots}
    findings: list[str] = []
    if set(observed) != selected or len(observed) != len(snapshots):
        findings.append("state_contradiction")
    internal: set[tuple[int, int]] = set()
    external: set[int] = set()
    for number in receipt.issues:
        snapshot = observed.get(number)
        if snapshot is None:
            continue
        contract = parse_issue_contract(snapshot.issue.body)
        if not snapshot.authoritative:
            findings.append("external_state_unavailable")
        if contract.kind != "leaf" or not contract.ok:
            findings.append("contract_incomplete")
        if snapshot.children or snapshot.issue.state != "OPEN":
            findings.append("state_contradiction")
        if len(snapshot.assignees) > 1 or (
            snapshot.assignees and snapshot.assignees != (receipt.owner,)
        ):
            findings.append("claim_conflict")
        recorded: list[ResolutionReceipt] = []
        for comment in snapshot.comments:
            if comment.author != receipt.owner:
                continue
            try:
                parsed = ResolutionReceipt.from_comment(comment.body)
            except (TypeError, ValueError, json.JSONDecodeError):
                findings.append("state_contradiction")
                continue
            if parsed is not None:
                recorded.append(parsed)
        if recorded and (len(recorded) != 1 or recorded[0] != receipt):
            findings.append("state_contradiction")
        elif require_recorded and not recorded:
            findings.append("state_contradiction")
        findings.extend(value for value in snapshot.provider_findings if value in BLOCKERS)
        for dependency in snapshot.blocked_by:
            if dependency.state == "CLOSED":
                continue
            if dependency.number in selected:
                internal.add((number, dependency.number))
            else:
                external.add(dependency.number)
    if external:
        findings.append("dependency_blocked")
    blockers = _ordered(findings)
    return ResolutionPlan(
        eligible=not blockers,
        issues=receipt.issues,
        internal_dependencies=tuple(sorted(internal)),
        external_blockers=tuple(sorted(external)),
        blockers=blockers,
        receipt=receipt,
    )


def close_resolution_findings(
    snapshots: list[OutcomeSnapshot] | tuple[OutcomeSnapshot, ...],
    receipt: ResolutionReceipt,
    health: FinalHealth,
) -> tuple[str, ...]:
    findings: list[str] = []
    observed = {snapshot.issue.number: snapshot for snapshot in snapshots}
    if (
        receipt.pull_request is None
        or set(observed) != set(receipt.issues)
        or len(observed) != len(snapshots)
    ):
        findings.append("state_contradiction")
    for number in receipt.issues:
        snapshot = observed.get(number)
        if snapshot is None:
            continue
        contract = parse_issue_contract(snapshot.issue.body)
        if not snapshot.authoritative:
            findings.append("external_state_unavailable")
        if contract.kind != "leaf" or not contract.ok:
            findings.append("contract_incomplete")
        if not contract.acceptance_complete or not health.verification_passed:
            findings.append("verification_failed")
        if snapshot.issue.state != "CLOSED":
            findings.append("state_contradiction")
        if snapshot.assignees != (receipt.owner,):
            findings.append("claim_conflict")
        if _open(snapshot.blocked_by):
            findings.append("dependency_blocked")
        findings.extend(value for value in snapshot.provider_findings if value in BLOCKERS)
        recorded: list[ResolutionReceipt] = []
        for comment in snapshot.comments:
            if comment.author != receipt.owner:
                continue
            try:
                parsed = ResolutionReceipt.from_comment(comment.body)
            except (TypeError, ValueError, json.JSONDecodeError):
                findings.append("state_contradiction")
                continue
            if parsed is not None:
                recorded.append(parsed)
        if len(recorded) != 1 or recorded[0] != receipt:
            findings.append("state_contradiction")
        prs = snapshot.closing_prs
        if len(prs) != 1 or prs[0].number != receipt.pull_request:
            findings.append("state_contradiction")
        elif not _pr_verified(prs[0]):
            findings.append("verification_failed")
        elif not health.head_sha or prs[0].head_sha != health.head_sha:
            findings.append("state_contradiction")
    if not health.integration_healthy:
        findings.append("integration_unhealthy")
    if not health.source_clean:
        findings.append("state_contradiction")
    return _ordered(findings)


@dataclass(frozen=True)
class ContractResult:
    kind: str
    ok: bool
    missing: tuple[str, ...]
    acceptance_total: int
    acceptance_complete: bool
    sections: Mapping[str, str]


def load_contract(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("contract must be a mapping")
    unknown = sorted(set(data) - _CONTRACT_KEYS)
    if unknown:
        raise ValueError("unknown contract key(s): " + ", ".join(unknown))
    missing = sorted(_CONTRACT_KEYS - set(data))
    if missing:
        raise ValueError("missing contract key(s): " + ", ".join(missing))
    if type(data["version"]) is not int or data["version"] != 2:
        raise ValueError("contract version must be 2")
    expected = {
        "public_skill": "start",
        "skills": list(SKILLS),
        "hard_triggers": list(HARD_TRIGGERS),
        "root_issue_sections": list(ROOT_ISSUE_SECTIONS),
        "leaf_issue_sections": list(LEAF_ISSUE_SECTIONS),
        "advisory_labels": ADVISORY_LABELS,
        "receipts": list(RECEIPTS),
        "blockers": list(BLOCKERS),
    }
    for key, value in expected.items():
        if data[key] != value:
            raise ValueError(f"contract {key} must equal {value}")
        if isinstance(data[key], list) and len(data[key]) != len(set(data[key])):
            raise ValueError(f"contract {key} contains duplicate values")
    return data


def _sections(body: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", body))
    result: dict[str, str] = {}
    duplicates: set[str] = set()
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        key = match.group(1).strip().casefold()
        if key in result:
            duplicates.add(key)
        result[key] = body[match.end():end].strip()
    for key in duplicates:
        result[key] = ""
    return result


def parse_issue_contract(body: str) -> ContractResult:
    found = _sections(body)
    root_present = any(name.casefold() in found for name in ROOT_ISSUE_SECTIONS)
    leaf_present = any(name.casefold() in found for name in LEAF_ISSUE_SECTIONS)
    if root_present and leaf_present:
        return ContractResult("mixed", False, ("mixed issue contract",), 0, False, {})
    if not root_present and not leaf_present:
        return ContractResult("unknown", False, ("root or leaf issue contract",), 0, False, {})
    kind = "root" if root_present else "leaf"
    expected = ROOT_ISSUE_SECTIONS if kind == "root" else LEAF_ISSUE_SECTIONS
    values = {name: found.get(name.casefold(), "") for name in expected}
    missing = [name for name, value in values.items() if not value]
    if kind == "root":
        stories = re.findall(r"(?m)^\s*\d+\.\s+\S", values["User Stories"])
        if not stories and "User Stories" not in missing:
            missing.append("User Stories")
        acceptance_total = len(stories)
        complete = not missing
    else:
        parent = values["Parent"]
        reference = r"(?:#[1-9]\d*|https://\S+/issues/[1-9]\d*)"
        if parent and re.search(reference, parent) is None:
            missing.append("Parent")
        blocked_by = values["Blocked by"]
        if (
            blocked_by
            and not blocked_by.casefold().startswith("none")
            and re.search(reference, blocked_by) is None
        ):
            missing.append("Blocked by")
        boxes = re.findall(r"(?im)^\s*[-*]\s*\[([ xX])\]\s+\S", values["Acceptance criteria"])
        if not boxes and "Acceptance criteria" not in missing:
            missing.append("Acceptance criteria")
        acceptance_total = len(boxes)
        complete = bool(boxes) and all(value.lower() == "x" for value in boxes)
    return ContractResult(kind, not missing, tuple(missing), acceptance_total, complete, values)


def _ordered(findings: list[str]) -> tuple[str, ...]:
    selected = set(findings)
    return tuple(value for value in BLOCKERS if value in selected)


def _open(items: tuple[Issue, ...]) -> bool:
    return any(item.state != "CLOSED" for item in items)


def _pr_verified(pr: PullRequest) -> bool:
    review_clear = pr.review_decision not in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}
    return pr.merged and pr.state == "MERGED" and pr.checks_complete and pr.checks_successful and review_clear


def closeout_findings(snapshot: OutcomeSnapshot, health: FinalHealth) -> tuple[str, ...]:
    findings = [value for value in snapshot.provider_findings if value in BLOCKERS]
    contract = parse_issue_contract(snapshot.issue.body)
    rollup = bool(snapshot.children)
    if not contract.ok:
        findings.append("contract_incomplete")
    if _open(snapshot.blocked_by):
        findings.append("dependency_blocked")
    if (not rollup and len(snapshot.assignees) != 1) or (rollup and len(snapshot.assignees) > 1):
        findings.append("claim_conflict")
    prs = snapshot.closing_prs
    if not contract.acceptance_complete or not health.verification_passed:
        findings.append("verification_failed")
    if not rollup and (len(prs) != 1 or (prs and not _pr_verified(prs[0]))):
        findings.append("verification_failed")
    incomplete_child = any(child.state != "CLOSED" or child.lifecycle_state != "Done" for child in snapshot.children)
    contradictory_child = any(child.state == "CLOSED" and child.lifecycle_state != "Done" for child in snapshot.children)
    if incomplete_child or not health.integration_healthy:
        findings.append("integration_unhealthy")
    if snapshot.issue.state != "CLOSED":
        findings.append("state_contradiction")
    elif rollup and prs:
        findings.append("state_contradiction")
    elif contradictory_child:
        findings.append("state_contradiction")
    elif not health.source_clean:
        findings.append("state_contradiction")
    elif not rollup and (len(prs) != 1 or not prs[0].merged or not health.head_sha or prs[0].head_sha != health.head_sha):
        findings.append("state_contradiction")
    if not snapshot.authoritative:
        findings.append("external_state_unavailable")
    return _ordered(findings)


def derive_state(snapshot: OutcomeSnapshot) -> str:
    if not snapshot.authoritative:
        return "Blocked"
    contract = parse_issue_contract(snapshot.issue.body)
    failed_pr = any(pr.checks_complete and not pr.checks_successful for pr in snapshot.closing_prs)
    missing_active_claim = not snapshot.children and bool(snapshot.closing_prs or snapshot.issue.state == "CLOSED") and len(snapshot.assignees) != 1
    blocked = (
        not contract.ok
        or _open(snapshot.blocked_by)
        or len(snapshot.assignees) > 1
        or missing_active_claim
        or bool(snapshot.provider_findings)
        or failed_pr
        or snapshot.issue.state == "CLOSED" and any(child.state != "CLOSED" or child.lifecycle_state != "Done" for child in snapshot.children)
    )
    if blocked:
        return "Blocked"
    if snapshot.issue.state == "CLOSED":
        if snapshot.children:
            complete = all(child.state == "CLOSED" and child.lifecycle_state == "Done" for child in snapshot.children)
            return "Done" if snapshot.authoritative and contract.acceptance_complete and complete else "Blocked"
        if (
            snapshot.authoritative
            and contract.acceptance_complete
            and len(snapshot.closing_prs) == 1
            and _pr_verified(snapshot.closing_prs[0])
            and not _open(snapshot.children)
        ):
            return "Done"
        return "Blocked"
    if snapshot.closing_prs:
        return "In review" if len(snapshot.closing_prs) == 1 and not snapshot.closing_prs[0].merged else "Blocked"
    if len(snapshot.assignees) == 1:
        return "Claimed"
    return "Ready"


@dataclass(frozen=True)
class OutcomeDigest:
    outcome: str
    ready_frontier: tuple[dict[str, Any], ...]
    active: Mapping[str, Any]
    blockers_or_decisions: tuple[str, ...]
    next_safe_action: str
    source: str
    source_urls: tuple[str, ...]
    observed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "ready_frontier": list(self.ready_frontier),
            "active": dict(self.active),
            "blockers_or_decisions": list(self.blockers_or_decisions),
            "next_safe_action": self.next_safe_action,
            "source": self.source,
            "source_urls": list(self.source_urls),
            "observed_at": self.observed_at,
        }


def derive_digest(snapshot: OutcomeSnapshot) -> OutcomeDigest:
    state = derive_state(snapshot)
    contract = parse_issue_contract(snapshot.issue.body)
    outcome_section = "Solution" if contract.kind == "root" else "What to build"
    outcome = next(
        (line.strip() for line in contract.sections.get(outcome_section, "").splitlines() if line.strip()),
        snapshot.issue.title,
    )
    candidates = snapshot.children if snapshot.children else (snapshot.issue,)
    ready = tuple(
        {"number": item.number, "title": item.title, "url": item.url}
        for item in candidates
        if snapshot.authoritative and item.state == "OPEN" and (item.lifecycle_state == "Ready" if snapshot.children else state == "Ready")
    )
    active: dict[str, Any] = {}
    if snapshot.assignees:
        active["owner"] = snapshot.assignees[0]
    if snapshot.closing_prs:
        active["pull_request"] = {"number": snapshot.closing_prs[0].number, "url": snapshot.closing_prs[0].url}
    blockers: list[str] = [value for value in snapshot.provider_findings if value in BLOCKERS]
    if not snapshot.authoritative:
        blockers.append("external_state_unavailable")
    if not contract.ok:
        blockers.append("contract_incomplete")
    if _open(snapshot.blocked_by):
        blockers.append("dependency_blocked")
    if len(snapshot.assignees) > 1:
        blockers.append("claim_conflict")
    child_blockers = [f"child #{item.number} is {item.lifecycle_state}" for item in snapshot.children if item.lifecycle_state == "Blocked"]
    active_child = next((item for item in snapshot.children if item.lifecycle_state in {"Claimed", "In review"}), None)
    if snapshot.children and active_child:
        active["issue"] = {"number": active_child.number, "title": active_child.title, "url": active_child.url, "state": active_child.lifecycle_state}
        next_action = f"Continue active child #{active_child.number}."
    elif snapshot.children and ready:
        next_action = f"Claim ready child #{ready[0]['number']} before implementation."
    elif snapshot.children and child_blockers:
        blocked_number = next(item.number for item in snapshot.children if item.lifecycle_state == "Blocked")
        next_action = f"Resolve blockers on child #{blocked_number} before continuing."
    elif snapshot.children:
        next_action = f"Verify rollup health before closing parent issue #{snapshot.issue.number}."
    elif state == "Ready":
        next_action = f"Claim ready issue #{snapshot.issue.number} before implementation."
    elif state == "Claimed":
        next_action = f"Continue claimed issue #{snapshot.issue.number}."
    elif state == "In review":
        next_action = f"Review pull request #{snapshot.closing_prs[0].number} and current checks."
    elif state == "Done":
        next_action = "No action; the current outcome is done."
    else:
        next_action = f"Resolve {(_ordered(blockers) or ('state_contradiction',))[0]} before continuing."
    return OutcomeDigest(
        outcome=outcome,
        ready_frontier=ready,
        active=active,
        blockers_or_decisions=(*_ordered(blockers), *child_blockers),
        next_safe_action=next_action,
        source="live" if snapshot.authoritative else "fixture",
        source_urls=snapshot.source_urls,
        observed_at=snapshot.observed_at,
    )
