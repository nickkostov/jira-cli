# src/cashout/issue.py
from __future__ import annotations
import json
import requests
from typing import Optional, Dict, Any, List
from typing import Tuple, List

from .auth import get_base_url, get_token, bearer_headers  # reuse auth helpers


def create_issue_simple(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: Optional[str] = None,
    labels: Optional[List[str]] = None,
    priority: Optional[str] = None,
    base_url_override: Optional[str] = None,
    token_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a Jira issue using Bearer auth (API v2) and return the response JSON.
    """
    base_url = (base_url_override or get_base_url())
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    url = f"{base_url.rstrip('/')}/rest/api/2/issue"
    fields: Dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }
    if description:
        fields["description"] = description
    if labels:
        fields["labels"] = labels
    if priority:
        fields["priority"] = {"name": priority}

    resp = requests.post(
        url,
        headers={"Content-Type": "application/json", "Accept": "application/json", **bearer_headers(token)},
        data=json.dumps({"fields": fields}),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def add_comment(
    issue_key: str,
    comment_body: str,
    base_url_override: Optional[str] = None,
    token_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add a comment to an existing Jira issue.
    """
    base_url = (base_url_override or get_base_url())
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    url = f"{base_url.rstrip('/')}/rest/api/2/issue/{issue_key}/comment"
    payload = {"body": comment_body}

    resp = requests.post(
        url,
        headers={"Content-Type": "application/json", "Accept": "application/json", **bearer_headers(token)},
        data=json.dumps(payload),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def search_issues(
    project_key: str,
    jql_extra: Optional[str] = None,
    only_open: bool = True,
    assignee: Optional[str] = None,
    mine: bool = False,
    fields: Optional[List[str]] = None,
    limit: int = 50,
    base_url_override: Optional[str] = None,
    token_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query Jira for issues with JQL. Returns the raw search payload:
    { "startAt": ..., "maxResults": ..., "total": ..., "issues": [...] }
    Pagination is handled internally up to `limit`.
    """
    base_url = (base_url_override or get_base_url())
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    # Build JQL
    jql_parts: List[str] = [f'project = "{project_key}"']
    if only_open:
        jql_parts.append("statusCategory != Done")
    if mine:
        jql_parts.append("assignee = currentUser()")
    elif assignee:
        # accept username or email; quotes allow spaces
        jql_parts.append(f'assignee = "{assignee}"')
    if jql_extra:
        jql_parts.append(f"({jql_extra})")
    jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

    # Fields
    fields = fields or ["key", "summary", "issuetype", "status", "assignee", "priority", "updated"]

    url = f"{base_url.rstrip('/')}/rest/api/2/search"
    headers = {"Accept": "application/json", "Content-Type": "application/json", **bearer_headers(token)}

    start_at = 0
    page_size = min(50, max(1, limit))
    all_issues: List[Dict[str, Any]] = []
    total = None

    while len(all_issues) < limit:
        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": min(page_size, limit - len(all_issues)),
            "fields": fields,
        }
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        total = data.get("total", 0)
        issues = data.get("issues", [])
        all_issues.extend(issues)
        if start_at + len(issues) >= total or not issues:
            break
        start_at += len(issues)

    return {"total": total or 0, "issues": all_issues}
