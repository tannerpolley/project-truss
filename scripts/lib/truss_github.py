"""Strict current-state GitHub observation for Project Truss."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping

try:
    from .truss_policy import OutcomeSnapshot, ResolutionReceipt, _assignees_match, _resolution_comment_evidence, derive_state, plan_resolution
except ImportError:  # public dispatcher imports scripts/lib as a top-level path
    from truss_policy import OutcomeSnapshot, ResolutionReceipt, _assignees_match, _resolution_comment_evidence, derive_state, plan_resolution


ISSUE_QUERY = """
query($owner:String!,$repo:String!,$number:Int!){
  repository(owner:$owner,name:$repo){
    issue(number:$number){
      id number title state body url updatedAt
      stateReason
      labels(first:100){nodes{name} pageInfo{hasNextPage endCursor}}
      assignees(first:100){nodes{login} pageInfo{hasNextPage endCursor}}
      milestone{number title state url}
      parent{number title state url}
      subIssues(first:100){nodes{id number title state body url} pageInfo{hasNextPage endCursor}}
      blockedBy(first:100){nodes{id number title state url} pageInfo{hasNextPage endCursor}}
      blocking(first:100){nodes{id number title state url} pageInfo{hasNextPage endCursor}}
      closedByPullRequestsReferences(first:100){nodes{number state merged mergedAt url headRefOid} pageInfo{hasNextPage endCursor}}
      comments(first:100){nodes{author{login} body createdAt url} pageInfo{hasNextPage endCursor}}
    }
  }
}
"""
PR_FIELDS = "number,state,mergedAt,mergeCommit,statusCheckRollup,reviewDecision,url,headRefOid"
MAX_PAGES = 20
_PAGE_FIELDS = {
    "labels": "nodes{name}",
    "assignees": "nodes{login}",
    "subIssues": "nodes{id number title state body url}",
    "blockedBy": "nodes{id number title state url}",
    "blocking": "nodes{id number title state url}",
    "closedByPullRequestsReferences": "nodes{number state merged mergedAt url headRefOid}",
    "comments": "nodes{author{login} body createdAt url}",
}


class GitHubObservationError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ProjectProjection:
    owner: str
    project: int
    url: str
    ensure: bool
    required: bool = False

    @classmethod
    def from_mapping(cls, data: Any) -> "ProjectProjection":
        fields = {"owner", "project", "url", "ensure"}
        if not isinstance(data, Mapping) or not fields.issubset(data) or set(data) - fields - {"required"}:
            raise ValueError("projection requires owner, project, url, and ensure; required is optional")
        if not isinstance(data["owner"], str) or not isinstance(data["url"], str):
            raise ValueError("projection owner and url must be strings")
        if type(data["ensure"]) is not bool:
            raise ValueError("projection ensure must be boolean")
        if "required" in data and type(data["required"]) is not bool:
            raise ValueError("projection required must be boolean")
        return cls(data["owner"], data["project"], data["url"], data["ensure"], data.get("required", False))


def project_commands(target: ProjectProjection, *, limit: int = 1000) -> dict[str, list[str]]:
    if not target.owner.strip() or type(target.project) is not int or target.project < 1 or not target.url.strip():
        raise ValueError("Project owner, positive project number, and item URL are required")
    if type(limit) is not int or limit < 1:
        raise ValueError("Project item-list limit must be positive")
    common = [str(target.project), "--owner", target.owner, "--format", "json"]
    return {"view": ["gh", "project", "view", *common],
            "list": ["gh", "project", "item-list", *common, "--limit", str(limit)],
            "add": ["gh", "project", "item-add", *common, "--url", target.url]}


def project_item_membership(payload: Mapping[str, Any], target_url: str) -> bool:
    items = payload.get("items")
    total = payload.get("totalCount")
    if not isinstance(items, list) or type(total) is not int or total < 0 or len(items) > total:
        raise GitHubObservationError("github_capability_missing", "Project item-list output is incomplete")
    matches = 0
    for item in items:
        if not isinstance(item, Mapping):
            raise GitHubObservationError("github_capability_missing", "Project item-list entry is malformed")
        content = item.get("content")
        observed = content.get("url") if isinstance(content, Mapping) else item.get("url")
        matches += observed == target_url
    if matches > 1:
        raise GitHubObservationError("github_capability_missing", "Project contains duplicate memberships")
    if total != len(items) and matches == 0:
        raise GitHubObservationError("github_scope_exceeded", "Project item-list did not include the target item")
    return matches == 1
def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _loads(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_strict_pairs)


def _default_runner(command: list[str], timeout: int):
    return subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)


def _clock() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class GitHubClient:
    def __init__(
        self,
        runner: Callable[[list[str], int], Any] = _default_runner,
        clock: Callable[[], str] = _clock,
    ) -> None:
        self.runner = runner
        self.clock = clock

    def _invoke(self, command: list[str], *, parse: bool = True) -> Any:
        try:
            result = self.runner(command, 30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitHubObservationError("external_state_unavailable", str(exc)) from exc
        if result.returncode:
            detail = (result.stderr or result.stdout or "GitHub command failed").strip()
            raise GitHubObservationError("external_state_unavailable", detail)
        if not parse:
            return None
        try:
            return _loads(result.stdout)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise GitHubObservationError("external_state_unavailable", f"invalid provider JSON: {exc}") from exc

    def _json(self, command: list[str]) -> Any:
        return self._invoke(command)

    def _mutate(self, command: list[str]) -> None:
        self._invoke(command, parse=False)

    def repository(self) -> str:
        value = self._json(["gh", "repo", "view", "--json", "nameWithOwner"])
        name = value.get("nameWithOwner") if isinstance(value, Mapping) else None
        if not isinstance(name, str) or "/" not in name:
            raise GitHubObservationError("github_capability_missing", "current GitHub repository is unavailable")
        return name.strip()

    def current_user(self) -> str:
        value = self._json(["gh", "api", "user"])
        login = value.get("login") if isinstance(value, Mapping) else None
        if not isinstance(login, str) or not login.strip():
            raise GitHubObservationError("github_capability_missing", "current GitHub user is unavailable")
        return login.strip()

    def project_membership(self, target: ProjectProjection) -> dict[str, Any]:
        commands = project_commands(target)
        try:
            view = self._json(commands["view"])
            if not isinstance(view, Mapping) or not isinstance(view.get("url"), str):
                raise GitHubObservationError("github_capability_missing", "Project URL is unavailable")
            member = False
            for limit in (1000, 5000):
                items = self._json(project_commands(target, limit=limit)["list"])
                if not isinstance(items, Mapping):
                    raise GitHubObservationError("github_capability_missing", "Project items are unavailable")
                try:
                    member = project_item_membership(items, target.url)
                    break
                except GitHubObservationError as exc:
                    if exc.code != "github_scope_exceeded" or limit == 5000:
                        raise
            if target.ensure and not member:
                self._json(commands["add"])
                refreshed = self._json(project_commands(target, limit=5000)["list"])
                if not isinstance(refreshed, Mapping):
                    raise GitHubObservationError("github_capability_missing", "Project items are unavailable")
                member = project_item_membership(refreshed, target.url)
                if not member:
                    raise GitHubObservationError("github_capability_missing", "Project membership was not verified")
            return {"project_url": view["url"], "item_url": target.url, "member": member, "required": target.required}
        except GitHubObservationError as exc:
            if not target.required:
                return {"project_url": None, "item_url": target.url, "member": False, "required": False, "advisory": str(exc)}
            raise GitHubObservationError(exc.code, str(exc)) from exc

    def pull_request_is_governed(self, repository: str, number: int) -> bool:
        if len(repository.split("/")) != 2 or not all(repository.split("/")) or type(number) is not int or number < 1:
            raise ValueError("repository must be OWNER/REPO and pull request must be a positive integer")
        payload = self._json(["gh", "pr", "view", str(number), "--repo", repository,
                              "--json", "number,headRefName,closingIssuesReferences"])
        if not isinstance(payload, Mapping) or not {"number", "headRefName", "closingIssuesReferences"}.issubset(payload):
            raise GitHubObservationError("github_capability_missing", "pull request fields are incomplete")
        refs, branch = payload["closingIssuesReferences"], payload["headRefName"]
        if payload["number"] != number or not isinstance(branch, str) or not isinstance(refs, list):
            raise GitHubObservationError("github_capability_missing", "pull request identity is malformed")
        for ref in refs:
            issue = ref.get("number") if isinstance(ref, Mapping) else None
            if type(issue) is not int:
                raise GitHubObservationError("github_capability_missing", "closing issue identity is missing")
            for comment in self.snapshot(repository, issue).comments:
                receipt = ResolutionReceipt.from_comment(comment.body)
                if receipt and comment.author == receipt.owner and issue in receipt.issues and receipt.branch == branch and receipt.pull_request in (None, number):
                    return True
        return False

    def claim_resolution(self, repository: str, receipt: ResolutionReceipt) -> dict[str, Any]:
        snapshots = [self.snapshot(repository, number) for number in receipt.issues]
        plan = plan_resolution(snapshots, receipt)
        if not plan.eligible:
            raise GitHubObservationError("claim_conflict", ", ".join(plan.blockers))
        assigned: list[int] = []
        try:
            for snapshot in snapshots:
                if not snapshot.assignees:
                    self._mutate([
                        "gh", "issue", "edit", str(snapshot.issue.number), "--repo", repository,
                        "--add-assignee", receipt.owner,
                    ])
                elif not _assignees_match(snapshot, receipt):
                    raise GitHubObservationError("claim_conflict", f"issue #{snapshot.issue.number} has another assignee")
                assigned.append(snapshot.issue.number)
            for snapshot in snapshots:
                recorded, _ = _resolution_comment_evidence(snapshot, receipt)
                if not recorded:
                    self._mutate([
                        "gh", "issue", "comment", str(snapshot.issue.number), "--repo", repository,
                        "--body", receipt.comment(),
                    ])
        except GitHubObservationError as exc:
            if assigned:
                raise GitHubObservationError("claim_partial", f"claim was partially written: {exc}") from exc
            raise
        verified = [self.snapshot(repository, number) for number in receipt.issues]
        result = plan_resolution(verified, receipt, require_recorded=True)
        if not result.eligible:
            raise GitHubObservationError("claim_partial", ", ".join(result.blockers))
        return {"issues": list(receipt.issues), "receipt": receipt.to_dict(), "verified": True}
    @staticmethod
    def _connection(issue: Mapping[str, Any], name: str) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
        value = issue.get(name)
        if not isinstance(value, Mapping) or not isinstance(value.get("nodes"), list):
            raise GitHubObservationError("github_capability_missing", f"missing {name} connection")
        page = value.get("pageInfo")
        if not isinstance(page, Mapping) or type(page.get("hasNextPage")) is not bool:
            raise GitHubObservationError("github_capability_missing", f"missing {name} pagination proof")
        if page["hasNextPage"] and not page.get("endCursor"):
            raise GitHubObservationError("github_capability_missing", f"missing {name} end cursor")
        return value["nodes"], page

    def _page(self, repository: str, issue_number: int, name: str, cursor: str) -> Mapping[str, Any]:
        parts = repository.split("/")
        query = f"""
query($owner:String!,$repo:String!,$number:Int!,$after:String){{
  repository(owner:$owner,name:$repo){{
    issue(number:$number){{
      {name}(first:100,after:$after){{{_PAGE_FIELDS[name]} pageInfo{{hasNextPage endCursor}}}}
    }}
  }}
}}
"""
        command = [
            "gh", "api", "graphql", "-f", f"query={query}",
            "-F", f"owner={parts[0]}", "-F", f"repo={parts[1]}", "-F", f"number={issue_number}",
            "-f", f"after={cursor}",
        ]
        payload = self._json(command)
        if not isinstance(payload, Mapping) or payload.get("errors"):
            raise GitHubObservationError("github_capability_missing", f"{name} pagination returned errors")
        try:
            node = payload["data"]["repository"]["issue"]
            value = node[name]
        except (KeyError, TypeError) as exc:
            raise GitHubObservationError("github_capability_missing", f"{name} pagination payload is absent") from exc
        if not isinstance(value, Mapping) or not isinstance(value.get("nodes"), list):
            raise GitHubObservationError("github_capability_missing", f"{name} pagination payload is malformed")
        return value

    def _paginate(self, repository: str, issue_number: int, name: str, nodes: list[Mapping[str, Any]], page: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        pages, cursor = 1, page.get("endCursor")
        while page.get("hasNextPage"):
            if pages >= MAX_PAGES or not isinstance(cursor, str) or not cursor:
                raise GitHubObservationError("github_scope_exceeded", f"{name} exceeds the safe pagination limit")
            value = self._page(repository, issue_number, name, cursor)
            page = value.get("pageInfo") if isinstance(value.get("pageInfo"), Mapping) else {}
            if not isinstance(page.get("hasNextPage"), bool):
                raise GitHubObservationError("github_capability_missing", f"{name} pagination proof is incomplete")
            if page["hasNextPage"] and not isinstance(page.get("endCursor"), str):
                raise GitHubObservationError("github_capability_missing", f"{name} pagination cursor is missing")
            nodes.extend(value["nodes"])
            cursor = page.get("endCursor")
            pages += 1
        return nodes

    @staticmethod
    def _issue(node: Mapping[str, Any]) -> dict[str, Any]:
        if not {"number", "title", "state", "url"}.issubset(node):
            raise GitHubObservationError("github_capability_missing", "issue relation fields are incomplete")
        labels = node.get("labels")
        label_names = [value["name"] for value in labels.get("nodes", [])
                       if isinstance(value, Mapping) and isinstance(value.get("name"), str)] if isinstance(labels, Mapping) and isinstance(labels.get("nodes"), list) else []
        return {
            "number": node["number"],
            "title": node["title"],
            "state": node["state"],
            "url": node["url"],
            "body": node.get("body") or "",
            "state_reason": str(node.get("stateReason") or "").upper(),
            "labels": label_names,
        }

    def _pull_request(self, repository: str, reference: Mapping[str, Any]) -> dict[str, Any]:
        number = reference.get("number")
        if type(number) is not int:
            raise GitHubObservationError("github_capability_missing", "closing pull request number is missing")
        payload = self._json([
            "gh", "pr", "view", str(number), "--repo", repository, "--json", PR_FIELDS,
        ])
        required = {"number", "state", "mergedAt", "reviewDecision", "url", "headRefOid"}
        if not isinstance(payload, Mapping) or not required.issubset(payload):
            raise GitHubObservationError("github_capability_missing", f"pull request #{number} fields are incomplete")
        checks = payload.get("statusCheckRollup") or []
        if not isinstance(checks, list):
            raise GitHubObservationError("github_capability_missing", f"pull request #{number} checks are unavailable")
        complete = bool(checks)
        successful = bool(checks)
        for check in checks:
            if not isinstance(check, Mapping):
                raise GitHubObservationError("github_capability_missing", f"pull request #{number} check is malformed")
            if check.get("__typename") == "CheckRun":
                complete &= check.get("status") == "COMPLETED"
                successful &= check.get("conclusion") in {"SUCCESS", "NEUTRAL", "SKIPPED"}
            else:
                complete &= check.get("state") in {"SUCCESS", "ERROR", "FAILURE"}
                successful &= check.get("state") == "SUCCESS"
        state = str(payload["state"]).upper()
        return {
            "number": payload["number"], "state": state, "url": payload["url"],
            "merged": state == "MERGED" and bool(payload["mergedAt"]), "merged_at": payload["mergedAt"],
            "head_sha": payload["headRefOid"], "checks_complete": complete, "checks_successful": successful,
            "review_decision": payload["reviewDecision"] or "",
        }

    def snapshot(self, repository: str, issue_number: int) -> OutcomeSnapshot:
        return self._snapshot(repository, issue_number, expand_children=True)

    def _snapshot(
        self,
        repository: str,
        issue_number: int,
        *,
        expand_children: bool,
    ) -> OutcomeSnapshot:
        parts = repository.split("/")
        if len(parts) != 2 or not all(parts) or type(issue_number) is not int or issue_number < 1:
            raise ValueError("repository must be OWNER/REPO and issue must be a positive integer")
        payload = self._json([
            "gh", "api", "graphql", "-f", f"query={ISSUE_QUERY}",
            "-F", f"owner={parts[0]}", "-F", f"repo={parts[1]}", "-F", f"number={issue_number}",
        ])
        if not isinstance(payload, Mapping) or payload.get("errors"):
            raise GitHubObservationError("github_capability_missing", "GraphQL returned errors")
        try:
            node = payload["data"]["repository"]["issue"]
        except (KeyError, TypeError) as exc:
            raise GitHubObservationError("github_capability_missing", "issue payload is absent") from exc
        required = {"number", "title", "state", "body", "url", "updatedAt", "assignees", "milestone", "parent", "subIssues", "blockedBy", "blocking", "closedByPullRequestsReferences", "comments"}
        if not isinstance(node, Mapping) or not required.issubset(node):
            raise GitHubObservationError("github_capability_missing", "issue fields are incomplete")
        connections = {}
        for name in ("labels", "assignees", "subIssues", "blockedBy", "blocking", "closedByPullRequestsReferences", "comments"):
            if name == "labels" and name not in node:
                connections[name] = []
                continue
            nodes, page = self._connection(node, name)
            connections[name] = self._paginate(repository, issue_number, name, nodes, page)
        labels = connections["labels"]
        assignees, children = connections["assignees"], connections["subIssues"]
        blocked_by, blocking = connections["blockedBy"], connections["blocking"]
        pr_refs, comments = connections["closedByPullRequestsReferences"], connections["comments"]
        assignee_logins = [value.get("login") if isinstance(value, Mapping) else None for value in assignees]
        if any(not isinstance(login, str) or not login.strip() for login in assignee_logins):
            raise GitHubObservationError("github_capability_missing", "assignee identity is missing")
        prs = [self._pull_request(repository, value) for value in pr_refs]
        issue = self._issue({**node, "labels": {"nodes": labels}})
        parent = self._issue(node["parent"]) if node["parent"] else None
        milestone = self._issue(node["milestone"]) if node["milestone"] else None
        urls = [issue["url"]]
        for value in [*children, *blocked_by, *blocking, *pr_refs, *comments]:
            if isinstance(value, Mapping) and value.get("url"):
                urls.append(str(value["url"]))
        if parent:
            urls.append(parent["url"])
        if milestone:
            urls.append(milestone["url"])
        child_issues = []
        for value in children:
            child = self._issue(value)
            if expand_children:
                child_snapshot = self._snapshot(
                    repository, int(child["number"]), expand_children=False
                )
                child["lifecycle_state"] = derive_state(child_snapshot)
                urls.extend(child_snapshot.source_urls)
            child_issues.append(child)
        snapshot = OutcomeSnapshot.from_mapping(
            {
                "authoritative": True,
                "observed_at": self.clock(),
                "repository": repository,
                "issue": issue,
                "assignees": assignee_logins,
                "children": child_issues,
                "blocked_by": [self._issue(value) for value in blocked_by],
                "blocking": [self._issue(value) for value in blocking],
                "closing_prs": prs,
                "comments": [
                    {
                        "author": (value.get("author") or {}).get("login") or "",
                        "body": value.get("body") or "",
                        "created_at": value.get("createdAt") or "",
                        "url": value.get("url") or "",
                    }
                    for value in comments
                ],
                "source_urls": list(dict.fromkeys(urls)),
                "provider_findings": [],
                "parent": parent,
                "milestone": milestone,
            }
        )
        return snapshot


def load_fixture(path: Path) -> OutcomeSnapshot:
    try:
        data = _loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise GitHubObservationError("external_state_unavailable", f"invalid fixture: {exc}") from exc
    if not isinstance(data, dict):
        raise GitHubObservationError("external_state_unavailable", "fixture must be a JSON object")
    data["authoritative"] = False
    return OutcomeSnapshot.from_mapping(data)
