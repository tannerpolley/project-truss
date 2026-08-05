"""Pure Project Truss planning and current-state lifecycle policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any, ClassVar, Mapping

import yaml


SKILLS = ("setup", "start", "shape", "resolve", "close", "advanced-user-input")
PUBLIC_SKILLS = SKILLS
INVOCABLE_METHODS = (
    "grilling", "tdd", "diagnosing-bugs", "research", "domain-modeling", "prototype",
    "resolving-merge-conflicts", "code-review", "codebase-design", "cutthroat-code-cleanup",
    "minimize-code-surface", "scientific-coding-and-testing", "wizard", "writing-for-agents",
)
ROUTED_METHODS = INVOCABLE_METHODS
HARD_TRIGGERS = ("release_or_milestone", "multiple_independent_units",
                 "multi_agent_delegation", "exceeds_safe_context")
LANES = ("auto", "direct", "light", "governed")
CHANGE_RISKS = ("low", "normal", "high", "structural")
ROOT_ISSUE_SECTIONS = (
    "Problem Statement", "Solution", "User Stories", "Implementation Decisions", "Testing Decisions",
    "Out of Scope", "Further Notes",
)
LEAF_ISSUE_SECTIONS = ("Parent", "What to build", "Acceptance criteria", "Blocked by")
STANDALONE_ISSUE_SECTIONS = ("What to build", "Acceptance criteria", "Blocked by")
ADVISORY_LABELS = {"ready_for_agent": "agent-shaped"}
RECEIPTS = ("claim", "blocker_or_decision", "handoff", "verified_closeout")
BLOCKERS = (
    "authority_required", "decision_required", "github_capability_missing", "github_scope_exceeded", "method_capability_missing",
    "contract_incomplete", "dependency_blocked", "claim_conflict", "claim_partial", "verification_failed",
    "integration_unhealthy", "state_contradiction", "external_state_unavailable", "context_required",
    "vocabulary_required",
)
_CONTRACT_KEYS = {
    "version", "public_skills", "skills", "hard_triggers", "root_issue_sections", "leaf_issue_sections",
    "standalone_issue_sections",
    "advisory_labels", "receipts", "blockers",
}
_SECTION_ALIASES = {
    alias: canonical
    for canonical, aliases in (
        ("problem statement", ("context", "problem", "problem statement")),
        ("acceptance criteria", ("acceptance", "acceptance criteria", "checks")),
        ("implementation decisions", ("implementation", "implementation decisions")),
        ("testing decisions", ("testing", "testing decisions")),
        ("further notes", ("notes", "further notes")),
        ("what to build", ("scope", "requirements", "build", "what to build")),
        ("blocked by", ("dependencies", "blocked", "blocked by")),
    )
    for alias in aliases
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
    mode: str = "auto"
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
    code_change: bool = False
    stable_behavior_change: bool = False
    scope_complete: bool = False
    change_risk: str = "normal"
    repository_profile: str = "general"
    grilling_decisions: tuple[str, ...] = ()
    shared_understanding_confirmation: str = ""
    failed_gate: str = ""
    required_methods: tuple[str, ...] = ()
    available_methods: tuple[str, ...] = ()
    start_entry: bool = False
    context_available: bool | None = None
    context_reviewed: bool = False
    context_files: tuple[str, ...] = ()
    context_terms: tuple[str, ...] = ()
    vocabulary_confirmed: bool = False
    manual_procedure: bool = False
    agent_document_change: bool = False
    design_change: bool = False
    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkRequest":
        values = _strict_mapping(data, set(cls.__dataclass_fields__), "work request")
        for name in (
            "explicit", "merge_or_publication", "release_or_milestone",
            "exceeds_safe_context", "material_decision_missing", "matt_configured",
            "new_outcome", "material_rescope", "code_change", "stable_behavior_change",
            "scope_complete", "start_entry", "context_reviewed", "vocabulary_confirmed",
            "manual_procedure", "agent_document_change", "design_change",
        ):
            if name in values:
                values[name] = _bool(values, name)
        if "context_available" in values and values["context_available"] is not None:
            values["context_available"] = _bool(values, "context_available")
        for name in ("independent_units", "delegated_owners"):
            if name in values:
                values[name] = _positive_int(values, name)
        for name in ("required_methods", "available_methods", "grilling_decisions", "context_files", "context_terms"):
            if name in values:
                values[name] = _strings(values, name)
        profile = values.get("repository_profile", "general")
        if not isinstance(profile, str) or profile not in {"general", "application-development", "scientific-computing"}:
            raise ValueError("invalid repository_profile")
        mode = values.get("mode", "auto")
        if not isinstance(mode, str) or mode not in LANES:
            raise ValueError("invalid mode")
        risk = values.get("change_risk", "normal")
        if not isinstance(risk, str) or risk not in CHANGE_RISKS:
            raise ValueError("invalid change_risk")
        failed_gate = values.get("failed_gate", "")
        if not isinstance(failed_gate, str) or failed_gate not in {"", "verification", "review"}:
            raise ValueError("invalid failed_gate")
        confirmation = values.get("shared_understanding_confirmation", "")
        if "shared_understanding_confirmation" in values and (not isinstance(confirmation, str) or not confirmation.strip()):
            raise ValueError("shared_understanding_confirmation must be non-empty")
        if confirmation:
            values["shared_understanding_confirmation"] = confirmation.strip()
        return cls(**values)


@dataclass(frozen=True)
class TrussPlan:
    lane: str
    layers: tuple[str, ...]
    question_required: bool
    blockers: tuple[str, ...] = ()
    next_skill: str | None = None
    method_routes: Mapping[str, str] | None = None
    context_status: str = "not_required"
    context_files: tuple[str, ...] = ()
    context_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        next_action = (
            f"stop: {self.blockers[0]}" if self.next_skill is None and self.blockers
            else "proceed directly" if not self.next_skill else f"invoke project-truss:{self.next_skill}"
        )
        return {
            "lane": self.lane, "layers": list(self.layers),
            "question_required": self.question_required, "blockers": list(self.blockers),
            "next_skill": self.next_skill,
            "context": {
                "status": self.context_status,
                "files": list(self.context_files),
                "terms": list(self.context_terms),
            },
            "next_action": next_action,
            "continuation": {
                "status": "blocked" if self.blockers else "continue",
                "lane": self.lane,
                "next_skill": self.next_skill,
                "next_action": next_action,
                "blockers": list(self.blockers),
                "evidence": {
                    "method_routes": dict(self.method_routes or {}),
                    "context": {
                        "status": self.context_status,
                        "files": list(self.context_files),
                        "terms": list(self.context_terms),
                    },
                },
                "safe_retry_count": 0,
            },
            "method_routes": dict(self.method_routes or {}),
        }


def _route_methods(
    required: set[str], available: tuple[str, ...], configured: bool
) -> dict[str, str]:
    def route(method: str) -> str:
        if method not in required:
            return "not_triggered"
        return "invocable" if configured and method in available else "missing"
    methods = (*ROUTED_METHODS, *sorted(required - set(ROUTED_METHODS)))
    return {method: route(method) for method in methods}


def all_method_routes(available: tuple[str, ...]) -> dict[str, str]:
    return {method: "invocable" if method in available else "not_triggered" for method in ROUTED_METHODS}


def _context_status(request: WorkRequest) -> str:
    if not request.start_entry:
        return "not_required"
    if request.context_available is None:
        return "not_observed"
    if not request.context_available:
        return "missing"
    return "reviewed" if request.context_reviewed else "review_required"


def plan_work(request: WorkRequest) -> TrussPlan:
    full_governance = any((
        request.release_or_milestone, request.independent_units > 1,
        request.delegated_owners > 1, request.exceeds_safe_context,
    ))
    lane = request.mode
    if full_governance:
        lane = "governed"
    elif lane == "auto":
        lane = "light" if request.explicit or request.merge_or_publication else "direct"
    if lane == "direct":
        context_required = request.start_entry and (
            request.context_available is None or not request.context_available or not request.context_reviewed
        )
        blockers = tuple(code for condition, code in (
            (context_required, "context_required"),
            (request.material_decision_missing, "decision_required"),
        ) if condition)
        return TrussPlan(
            "direct", (), bool(blockers), blockers,
            next_skill="start" if context_required else "advanced-user-input" if blockers else None,
            method_routes=_route_methods(set(), (), False),
            context_status=_context_status(request),
            context_files=request.context_files,
            context_terms=request.context_terms,
        )
    if lane == "light":
        layers = ["issue", "pull_request"]
    else:
        layers = ["leaf", "pull_request"]
    if request.independent_units > 1:
        layers.insert(0, "parent")
    if lane == "governed" and request.release_or_milestone and request.independent_units > 1:
        layers.insert(0, "milestone")
    if lane == "governed" and not request.matt_configured:
        return TrussPlan(
            "governed", tuple(layers), request.material_decision_missing,
            next_skill="setup",
            method_routes=_route_methods(set(), (), False),
            context_status=_context_status(request),
            context_files=request.context_files,
            context_terms=request.context_terms,
        )
    required = set(request.required_methods)
    if lane == "governed" and (request.new_outcome or request.material_rescope):
        required.update(("grilling", "domain-modeling"))
    if request.code_change:
        if lane != "direct":
            required.add("code-review")
        if request.change_risk in {"high", "structural"}:
            required.update(("cutthroat-code-cleanup", "minimize-code-surface"))
    if request.stable_behavior_change and request.change_risk != "low":
        required.add("tdd")
    if request.code_change and request.repository_profile == "scientific-computing":
        required.add("scientific-coding-and-testing")
    if request.failed_gate:
        required.add("diagnosing-bugs")
    if request.manual_procedure:
        required.add("wizard")
    if request.agent_document_change:
        required.add("writing-for-agents")
    if request.design_change:
        required.add("codebase-design")
    wayfinding = lane == "governed" and request.exceeds_safe_context and request.material_decision_missing
    routes = _route_methods(required, request.available_methods, request.matt_configured)
    context_required = request.start_entry and (
        request.context_available is None or not request.context_available or not request.context_reviewed
    )
    vocabulary_required = lane == "governed" and (request.new_outcome or request.material_rescope) and not context_required and not request.vocabulary_confirmed
    grilling_due = lane == "governed" and (request.new_outcome or request.material_rescope) and not request.scope_complete and (
        not request.grilling_decisions or not request.shared_understanding_confirmation
    ) and not context_required and not vocabulary_required
    blockers = tuple(
        code for condition, code in (
            (context_required, "context_required"),
            (vocabulary_required, "vocabulary_required"),
            (lane == "governed" and "missing" in routes.values(), "method_capability_missing"),
            (grilling_due, "decision_required"),
        ) if condition
    )
    next_skill = (
        None
        if "method_capability_missing" in blockers
        else "start"
        if context_required or vocabulary_required or wayfinding or grilling_due
        else "advanced-user-input"
        if request.material_decision_missing
        else "shape"
        if lane == "governed" and (request.new_outcome or request.material_rescope)
        else None
    )
    context_status = "vocabulary_required" if vocabulary_required else _context_status(request)
    return TrussPlan(
        lane, tuple(layers), request.material_decision_missing or context_required or vocabulary_required or grilling_due,
        blockers, next_skill, routes, context_status, request.context_files, request.context_terms,
    )


def is_wayfinder_issue(body: str) -> bool:
    headings = tuple(value.strip().casefold() for value in re.findall(r"(?m)^##\s+(.+?)\s*$", body))
    return headings == ("question",) or headings == (
        "destination", "notes", "decisions so far", "not yet specified", "out of scope"
    )


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    state: str
    url: str
    body: str = ""
    lifecycle_state: str | None = None
    state_reason: str = ""
    labels: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Issue":
        return cls(int(data["number"]), str(data["title"]), str(data["state"]).upper(), str(data["url"]),
                   str(data.get("body") or ""), str(data["lifecycle_state"]) if data.get("lifecycle_state") else None,
                   str(data.get("state_reason") or "").upper(), tuple(str(value) for value in data.get("labels", [])))


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
        return cls(int(data["number"]), str(data["state"]).upper(), str(data["url"]), _bool(data, "merged"),
                   str(data["merged_at"]) if data.get("merged_at") else None, str(data.get("head_sha") or ""),
                   _bool(data, "checks_complete"), _bool(data, "checks_successful"), str(data.get("review_decision") or ""))


@dataclass(frozen=True)
class Comment:
    author: str
    body: str
    created_at: str
    url: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Comment":
        return cls(str(data.get("author") or ""), str(data.get("body") or ""),
                   str(data.get("created_at") or ""), str(data.get("url") or ""))


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
        children = (Issue.from_mapping(value) for value in data.get("children", []))
        return cls(_bool(data, "authoritative"), str(data.get("observed_at") or ""), str(data["repository"]),
                   Issue.from_mapping(data["issue"]), tuple(str(value) for value in data.get("assignees", [])),
                   tuple(child for child in children if not is_wayfinder_issue(child.body)),
                   tuple(Issue.from_mapping(value) for value in data.get("blocked_by", [])),
                   tuple(Issue.from_mapping(value) for value in data.get("blocking", [])),
                   tuple(PullRequest.from_mapping(value) for value in data.get("closing_prs", [])),
                   tuple(Comment.from_mapping(value) for value in data.get("comments", [])),
                   tuple(str(value) for value in data.get("source_urls", [])),
                   tuple(str(value) for value in data.get("provider_findings", [])),
                   Issue.from_mapping(data["parent"]) if data.get("parent") else None,
                   Issue.from_mapping(data["milestone"]) if data.get("milestone") else None)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in ("assignees", "children", "blocked_by", "blocking", "closing_prs", "comments", "source_urls", "provider_findings"):
            result[key] = list(result[key])
        result["issue"]["labels"] = list(result["issue"]["labels"])
        return result


@dataclass(frozen=True)
class FinalHealth:
    verification_passed: bool
    integration_healthy: bool
    source_clean: bool
    head_sha: str
    review_passed: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "FinalHealth":
        values = _strict_mapping(data, set(cls.__dataclass_fields__), "final health")
        return cls(_bool(values, "verification_passed"), _bool(values, "integration_healthy"),
                   _bool(values, "source_clean"), str(values.get("head_sha") or ""), _bool(values, "review_passed"))


@dataclass(frozen=True)
class ResolutionReceipt:
    issues: tuple[int, ...]
    owner: str
    implementation_base: str
    branch: str
    worktree: str
    pull_request: int | None = None
    collaborators: tuple[str, ...] = ()
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
        if not Path(worktree).is_absolute():
            raise ValueError("worktree must be an absolute path")
        if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", implementation_base) is None:
            raise ValueError("implementation_base must be a full Git commit hash")
        pull_request = values.get("pull_request")
        if pull_request is not None and (type(pull_request) is not int or pull_request < 1):
            raise ValueError("pull_request must be a positive integer")
        raw_collaborators = values.get("collaborators", ())
        if not isinstance(raw_collaborators, (list, tuple)) or any(not isinstance(value, str) or not value.strip() for value in raw_collaborators):
            raise ValueError("collaborators must be an array of non-empty strings")
        collaborators = tuple(sorted(value.strip() for value in raw_collaborators))
        if len(collaborators) != len(set(collaborators)) or owner in collaborators:
            raise ValueError("collaborators must be unique and must not include owner")
        return cls(tuple(sorted(issues)), owner, implementation_base, branch, worktree, pull_request, collaborators)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "issues": list(self.issues),
            "owner": self.owner,
            "implementation_base": self.implementation_base,
            "branch": self.branch,
            "worktree": self.worktree,
            "pull_request": self.pull_request,
        }
        if self.collaborators:
            result["collaborators"] = list(self.collaborators)
        return result

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
        return {"eligible": self.eligible, "issues": list(self.issues),
                "internal_dependencies": [{"blocked": a, "blocked_by": b} for a, b in self.internal_dependencies],
                "external_blockers": list(self.external_blockers), "blockers": list(self.blockers),
                "receipt": self.receipt.to_dict()}


def _resolution_comment_evidence(
    snapshot: OutcomeSnapshot, receipt: ResolutionReceipt,
) -> tuple[tuple[ResolutionReceipt, ...], tuple[str, ...]]:
    recorded: list[ResolutionReceipt] = []
    findings: list[str] = []
    for comment in snapshot.comments:
        try:
            parsed = ResolutionReceipt.from_comment(comment.body)
        except (TypeError, ValueError, json.JSONDecodeError):
            findings.append("state_contradiction")
            continue
        if parsed is None:
            continue
        if comment.author != receipt.owner:
            findings.append("claim_conflict")
        else:
            recorded.append(parsed)
    return tuple(recorded), _ordered(findings)


def _assignees_match(snapshot: OutcomeSnapshot, receipt: ResolutionReceipt) -> bool:
    assignees = snapshot.assignees
    if not receipt.collaborators:
        return assignees == (receipt.owner,)
    allowed = {receipt.owner, *receipt.collaborators}
    return bool(assignees) and receipt.owner in assignees and len(assignees) == len(set(assignees)) and set(assignees) <= allowed


def _has_valid_claim(snapshot: OutcomeSnapshot) -> bool:
    if len(snapshot.assignees) == 1:
        return True
    for comment in snapshot.comments:
        try:
            receipt = ResolutionReceipt.from_comment(comment.body)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if receipt and comment.author == receipt.owner and _assignees_match(snapshot, receipt):
            return True
    return False


def _resolution_evidence_findings(
    snapshot: OutcomeSnapshot, receipt: ResolutionReceipt, *, require_recorded: bool,
) -> tuple[str, ...]:
    recorded, findings = _resolution_comment_evidence(snapshot, receipt)
    values = list(findings)
    if recorded and (len(recorded) != 1 or recorded[0] != receipt):
        values.append("state_contradiction")
    elif require_recorded and not recorded:
        values.append("state_contradiction")
    prs = snapshot.closing_prs
    if receipt.pull_request is None and prs:
        values.append("state_contradiction")
    elif receipt.pull_request is not None and (len(prs) != 1 or prs[0].number != receipt.pull_request):
        values.append("state_contradiction")
    return _ordered(values)


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
        if contract.kind not in {"leaf", "standalone"} or not contract.ok:
            findings.append("contract_incomplete")
        if snapshot.children or snapshot.issue.state != "OPEN":
            findings.append("state_contradiction")
        if (require_recorded and not _assignees_match(snapshot, receipt)) or (
            not require_recorded and snapshot.assignees and not _assignees_match(snapshot, receipt)
        ):
            findings.append("claim_conflict")
        findings.extend(_resolution_evidence_findings(
            snapshot, receipt, require_recorded=require_recorded))
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
        if contract.kind not in {"leaf", "standalone"} or not contract.ok:
            findings.append("contract_incomplete")
        if (
            not contract.acceptance_complete
            or not health.verification_passed
            or not health.review_passed
        ):
            findings.append("verification_failed")
        if snapshot.issue.state != "CLOSED":
            findings.append("state_contradiction")
        if not _assignees_match(snapshot, receipt):
            findings.append("claim_conflict")
        if _open(snapshot.blocked_by):
            findings.append("dependency_blocked")
        findings.extend(value for value in snapshot.provider_findings if value in BLOCKERS)
        findings.extend(_resolution_evidence_findings(
            snapshot, receipt, require_recorded=True))
        prs = snapshot.closing_prs
        if len(prs) == 1 and prs[0].number == receipt.pull_request and not _pr_verified(prs[0]):
            findings.append("verification_failed")
        elif len(prs) == 1 and prs[0].number == receipt.pull_request and (
            not health.head_sha or prs[0].head_sha != health.head_sha
        ):
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
        "public_skills": list(PUBLIC_SKILLS),
        "skills": list(SKILLS),
        "hard_triggers": list(HARD_TRIGGERS),
        "root_issue_sections": list(ROOT_ISSUE_SECTIONS),
        "leaf_issue_sections": list(LEAF_ISSUE_SECTIONS),
        "standalone_issue_sections": list(STANDALONE_ISSUE_SECTIONS),
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
        raw_key = match.group(1).strip().casefold()
        key = _SECTION_ALIASES.get(raw_key, raw_key)
        if key in result:
            duplicates.add(key)
        result[key] = body[match.end():end].strip()
    for key in duplicates:
        result[key] = ""
    return result


def parse_issue_contract(body: str) -> ContractResult:
    if is_wayfinder_issue(body):
        return ContractResult("wayfinder", False, ("execution issue contract",), 0, False, {})
    if re.search(r"(?im)^\s*#{1,6}\s+(?:question|destination|decisions so far|not yet specified)\s*$", body):
        return ContractResult("mixed", False, ("wayfinder and execution contract",), 0, False, {})
    found = _sections(body)
    root_present = any(name.casefold() in found for name in ROOT_ISSUE_SECTIONS if name != "Further Notes")
    standalone_present = any(name.casefold() in found for name in STANDALONE_ISSUE_SECTIONS)
    parent_present = "parent" in found
    if root_present and standalone_present:
        return ContractResult("mixed", False, ("mixed issue contract",), 0, False, {})
    if not root_present and not standalone_present:
        return ContractResult("unknown", False, ("root or standalone issue contract",), 0, False, {})
    kind = "root" if root_present else "leaf" if parent_present else "standalone"
    expected = ROOT_ISSUE_SECTIONS if kind == "root" else LEAF_ISSUE_SECTIONS if kind == "leaf" else STANDALONE_ISSUE_SECTIONS
    values = {name: found.get(name.casefold(), "") for name in expected}
    missing = [name for name, value in values.items() if not value]
    if kind == "root":
        stories = re.findall(r"(?m)^\s*\d+\.\s+\S", values["User Stories"])
        if not stories and "User Stories" not in missing:
            missing.append("User Stories")
        acceptance_total = len(stories)
        complete = not missing
    else:
        if kind == "leaf":
            parent = values["Parent"]
            reference = r"(?:#[1-9]\d*|https://\S+/issues/[1-9]\d*)"
            if parent and re.search(reference, parent) is None:
                missing.append("Parent")
            blocked_by = values["Blocked by"]
            if blocked_by and not blocked_by.casefold().startswith("none") and re.search(reference, blocked_by) is None:
                missing.append("Blocked by")
        boxes = re.findall(r"(?im)^\s*[-*]\s*\[([ xX])\]\s+\S", values["Acceptance criteria"])
        if not boxes and "Acceptance criteria" not in missing:
            missing.append("Acceptance criteria")
        acceptance_total, complete = len(boxes), bool(boxes) and all(value.lower() == "x" for value in boxes)
    return ContractResult(kind, not missing, tuple(missing), acceptance_total, complete, values)


def _ordered(findings: list[str]) -> tuple[str, ...]:
    selected = set(findings)
    return tuple(value for value in BLOCKERS if value in selected)


def _open(items: tuple[Issue, ...]) -> bool:
    return any(item.state != "CLOSED" for item in items)


def _terminal_state(issue: Issue) -> str | None:
    raw = issue.state_reason or ""
    match = re.search(r"(?im)^\s*##\s+Disposition\s*$\n+\s*([^\n]+)", issue.body)
    value = (match.group(1) if match else raw).strip().casefold().replace("_", " ")
    if value in {"not planned", "cancelled", "canceled", "won't do", "wont do"}:
        return "Cancelled"
    if value == "deferred":
        return "Deferred"
    return None


def _pr_verified(pr: PullRequest) -> bool:
    review_clear = pr.review_decision not in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}
    return pr.merged and pr.state == "MERGED" and review_clear


def closeout_findings(snapshot: OutcomeSnapshot, health: FinalHealth) -> tuple[str, ...]:
    findings = [value for value in snapshot.provider_findings if value in BLOCKERS]
    contract = parse_issue_contract(snapshot.issue.body)
    rollup = bool(snapshot.children)
    if not contract.ok:
        findings.append("contract_incomplete")
    if _open(snapshot.blocked_by):
        findings.append("dependency_blocked")
    if (not rollup and not _has_valid_claim(snapshot)) or (rollup and len(snapshot.assignees) > 1):
        findings.append("claim_conflict")
    prs = snapshot.closing_prs
    if (
        not contract.acceptance_complete
        or not health.verification_passed
        or not rollup and not health.review_passed
    ):
        findings.append("verification_failed")
    if not rollup and (len(prs) != 1 or (prs and not _pr_verified(prs[0]))):
        findings.append("verification_failed")
    terminal_children = {"Done", "Cancelled", "Deferred"}
    incomplete_child = any(child.state != "CLOSED" or child.lifecycle_state not in terminal_children for child in snapshot.children)
    contradictory_child = any(child.state == "CLOSED" and child.lifecycle_state not in terminal_children for child in snapshot.children)
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
    terminal = _terminal_state(snapshot.issue)
    if snapshot.issue.state == "CLOSED" and terminal:
        return terminal
    contract = parse_issue_contract(snapshot.issue.body)
    missing_active_claim = not snapshot.children and bool(snapshot.closing_prs or snapshot.issue.state == "CLOSED") and not _has_valid_claim(snapshot)
    blocked = (
        not contract.ok
        or _open(snapshot.blocked_by)
        or len(snapshot.assignees) > 1 and not _has_valid_claim(snapshot)
        or missing_active_claim
        or bool(snapshot.provider_findings)
        or snapshot.issue.state == "CLOSED" and any(
            child.state != "CLOSED" or child.lifecycle_state not in {"Done", "Cancelled", "Deferred"}
            for child in snapshot.children
        )
    )
    if blocked:
        return "Blocked"
    if snapshot.issue.state == "CLOSED":
        if snapshot.children:
            complete = all(
                child.state == "CLOSED" and child.lifecycle_state in {"Done", "Cancelled", "Deferred"}
                for child in snapshot.children
            )
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
        return {"outcome": self.outcome, "ready_frontier": list(self.ready_frontier), "active": dict(self.active),
                "blockers_or_decisions": list(self.blockers_or_decisions), "next_safe_action": self.next_safe_action,
                "source": self.source, "source_urls": list(self.source_urls), "observed_at": self.observed_at}


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
    if len(snapshot.assignees) > 1 and not _has_valid_claim(snapshot):
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
        next_action = f"Review pull request #{snapshot.closing_prs[0].number} and current GitHub evidence."
    elif state == "Done":
        next_action = "No action; the current outcome is done."
    elif state in {"Cancelled", "Deferred"}:
        next_action = f"No action; the current outcome is {state.casefold()}."
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
