"""Strict current-state GitHub observation for Project Truss."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping

try:
    from .truss_policy import OutcomeSnapshot, derive_state
except ImportError:  # public dispatcher imports scripts/lib as a top-level path
    from truss_policy import OutcomeSnapshot, derive_state


API_VERSION = "2026-03-10"
ISSUE_QUERY = """
query($owner:String!,$repo:String!,$number:Int!){
  repository(owner:$owner,name:$repo){
    issue(number:$number){
      id number title state body url updatedAt
      assignees(first:10){nodes{login} pageInfo{hasNextPage}}
      milestone{number title state url}
      parent{number title state url}
      subIssues(first:100){nodes{id number title state body url} pageInfo{hasNextPage}}
      blockedBy(first:100){nodes{id number title state url} pageInfo{hasNextPage}}
      blocking(first:100){nodes{id number title state url} pageInfo{hasNextPage}}
      closedByPullRequestsReferences(first:20){nodes{number state merged mergedAt url headRefOid} pageInfo{hasNextPage}}
      comments(first:100){nodes{author{login} body createdAt url} pageInfo{hasNextPage}}
    }
  }
}
"""
PR_FIELDS = "number,state,mergedAt,mergeCommit,statusCheckRollup,reviewDecision,url,headRefOid"


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

    @classmethod
    def from_mapping(cls, data: Any) -> "ProjectProjection":
        if not isinstance(data, Mapping) or set(data) != {"owner", "project", "url", "ensure"}:
            raise ValueError("projection requires exactly owner, project, url, and ensure")
        if not isinstance(data["owner"], str) or not isinstance(data["url"], str):
            raise ValueError("projection owner and url must be strings")
        if type(data["ensure"]) is not bool:
            raise ValueError("projection ensure must be boolean")
        return cls(data["owner"], data["project"], data["url"], data["ensure"])


def project_commands(target: ProjectProjection) -> dict[str, list[str]]:
    if not target.owner.strip() or type(target.project) is not int or target.project < 1 or not target.url.strip():
        raise ValueError("Project owner, positive project number, and item URL are required")
    common = [str(target.project), "--owner", target.owner, "--format", "json"]
    return {"view": ["gh", "project", "view", *common],
            "list": ["gh", "project", "item-list", *common, "--limit", "1000"],
            "add": ["gh", "project", "item-add", *common, "--url", target.url]}


def project_item_membership(payload: Mapping[str, Any], target_url: str) -> bool:
    items = payload.get("items")
    total = payload.get("totalCount")
    if not isinstance(items, list) or type(total) is not int or total < 0:
        raise GitHubObservationError("github_capability_missing", "Project item-list output is incomplete")
    if total != len(items):
        raise GitHubObservationError("github_capability_missing", "Project item-list output is truncated")
    matches = 0
    for item in items:
        if not isinstance(item, Mapping):
            raise GitHubObservationError("github_capability_missing", "Project item-list entry is malformed")
        content = item.get("content")
        observed = content.get("url") if isinstance(content, Mapping) else item.get("url")
        matches += observed == target_url
    if matches > 1:
        raise GitHubObservationError("github_capability_missing", "Project contains duplicate memberships")
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

    def _json(self, command: list[str]) -> Any:
        try:
            result = self.runner(command, 30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitHubObservationError("external_state_unavailable", str(exc)) from exc
        if result.returncode:
            detail = (result.stderr or result.stdout or "GitHub command failed").strip()
            raise GitHubObservationError("external_state_unavailable", detail)
        try:
            return _loads(result.stdout)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise GitHubObservationError("external_state_unavailable", f"invalid provider JSON: {exc}") from exc

    def project_membership(self, target: ProjectProjection) -> dict[str, Any]:
        commands = project_commands(target)
        try:
            view = self._json(commands["view"])
            if not isinstance(view, Mapping) or not isinstance(view.get("url"), str):
                raise GitHubObservationError("github_capability_missing", "Project URL is unavailable")
            items = self._json(commands["list"])
            if not isinstance(items, Mapping):
                raise GitHubObservationError("github_capability_missing", "Project items are unavailable")
            member = project_item_membership(items, target.url)
            if target.ensure and not member:
                self._json(commands["add"])
                refreshed = self._json(commands["list"])
                if not isinstance(refreshed, Mapping):
                    raise GitHubObservationError("github_capability_missing", "Project items are unavailable")
                member = project_item_membership(refreshed, target.url)
                if not member:
                    raise GitHubObservationError(
                        "github_capability_missing", "Project membership was not verified"
                    )
            return {"project_url": view["url"], "item_url": target.url, "member": member}
        except GitHubObservationError as exc:
            raise GitHubObservationError("github_capability_missing", str(exc)) from exc
    @staticmethod
    def _connection(issue: Mapping[str, Any], name: str) -> list[Mapping[str, Any]]:
        value = issue.get(name)
        if not isinstance(value, Mapping) or not isinstance(value.get("nodes"), list):
            raise GitHubObservationError("github_capability_missing", f"missing {name} connection")
        page = value.get("pageInfo")
        if not isinstance(page, Mapping) or type(page.get("hasNextPage")) is not bool:
            raise GitHubObservationError("github_capability_missing", f"missing {name} pagination proof")
        if page["hasNextPage"]:
            raise GitHubObservationError("github_capability_missing", f"{name} exceeds supported page size")
        return value["nodes"]

    @staticmethod
    def _issue(node: Mapping[str, Any]) -> dict[str, Any]:
        required = {"number", "title", "state", "url"}
        if not required.issubset(node):
            raise GitHubObservationError("github_capability_missing", "issue relation fields are incomplete")
        return {
            "number": node["number"],
            "title": node["title"],
            "state": node["state"],
            "url": node["url"],
            "body": node.get("body") or "",
        }

    def _pull_request(self, repository: str, reference: Mapping[str, Any]) -> dict[str, Any]:
        number = reference.get("number")
        if type(number) is not int:
            raise GitHubObservationError("github_capability_missing", "closing pull request number is missing")
        payload = self._json(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--repo",
                repository,
                "--json",
                PR_FIELDS,
            ]
        )
        required = {"number", "state", "mergedAt", "statusCheckRollup", "reviewDecision", "url", "headRefOid"}
        if not isinstance(payload, Mapping) or not required.issubset(payload):
            raise GitHubObservationError("github_capability_missing", f"pull request #{number} fields are incomplete")
        checks = payload["statusCheckRollup"]
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
            "number": payload["number"],
            "state": state,
            "url": payload["url"],
            "merged": state == "MERGED" and bool(payload["mergedAt"]),
            "merged_at": payload["mergedAt"],
            "head_sha": payload["headRefOid"],
            "checks_complete": complete,
            "checks_successful": successful,
            "review_decision": payload["reviewDecision"] or "",
        }

    def snapshot(self, repository: str, issue_number: int) -> OutcomeSnapshot:
        return self._snapshot(repository, issue_number, expand_children=True)

    def _snapshot(self, repository: str, issue_number: int, *, expand_children: bool) -> OutcomeSnapshot:
        parts = repository.split("/")
        if len(parts) != 2 or not all(parts) or type(issue_number) is not int or issue_number < 1:
            raise ValueError("repository must be OWNER/REPO and issue must be a positive integer")
        payload = self._json(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={ISSUE_QUERY}",
                "-F",
                f"owner={parts[0]}",
                "-F",
                f"repo={parts[1]}",
                "-F",
                f"number={issue_number}",
            ]
        )
        if not isinstance(payload, Mapping) or payload.get("errors"):
            raise GitHubObservationError("github_capability_missing", "GraphQL returned errors")
        try:
            node = payload["data"]["repository"]["issue"]
        except (KeyError, TypeError) as exc:
            raise GitHubObservationError("github_capability_missing", "issue payload is absent") from exc
        required = {"number", "title", "state", "body", "url", "updatedAt", "assignees", "milestone", "parent", "subIssues", "blockedBy", "blocking", "closedByPullRequestsReferences", "comments"}
        if not isinstance(node, Mapping) or not required.issubset(node):
            raise GitHubObservationError("github_capability_missing", "issue fields are incomplete")
        assignees = self._connection(node, "assignees")
        children = self._connection(node, "subIssues")
        blocked_by = self._connection(node, "blockedBy")
        blocking = self._connection(node, "blocking")
        pr_refs = self._connection(node, "closedByPullRequestsReferences")
        comments = self._connection(node, "comments")
        assignee_logins = []
        for value in assignees:
            login = value.get("login") if isinstance(value, Mapping) else None
            if not isinstance(login, str) or not login.strip():
                raise GitHubObservationError("github_capability_missing", "assignee identity is missing")
            assignee_logins.append(login)
        prs = [self._pull_request(repository, value) for value in pr_refs]
        issue = self._issue(node)
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
                child_snapshot = self._snapshot(repository, int(child["number"]), expand_children=False)
                child["lifecycle_state"] = derive_state(child_snapshot)
                urls.extend(child_snapshot.source_urls)
            child_issues.append(child)
        return OutcomeSnapshot.from_mapping(
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


def load_fixture(path: Path) -> OutcomeSnapshot:
    try:
        data = _loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise GitHubObservationError("external_state_unavailable", f"invalid fixture: {exc}") from exc
    if not isinstance(data, dict):
        raise GitHubObservationError("external_state_unavailable", "fixture must be a JSON object")
    data["authoritative"] = False
    return OutcomeSnapshot.from_mapping(data)
