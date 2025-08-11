# src/cashout/issue.py
from __future__ import annotations
import json
import requests # type: ignore
import os
from typing import Optional, Dict, Any, List, Tuple

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

def assign_issue(
    issue_key: str,
    user: Optional[str] = None,
    account_id: Optional[str] = None,
    base_url_override: Optional[str] = None,
    token_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assign an issue.
    Jira API v2 supports:
      - {"name": "<username>"}      # Server/DC
      - {"accountId": "<accountId>"}# Cloud/DC (if enabled)
    """
    base_url = (base_url_override or get_base_url())
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    if not account_id and not user:
        raise RuntimeError("Provide --account-id or --user to assign.")

    url = f"{base_url.rstrip('/')}/rest/api/2/issue/{issue_key}/assignee"
    payload: Dict[str, Any] = {"accountId": account_id} if account_id else {"name": user}

    resp = requests.put(
        url,
        headers={"Accept": "application/json", "Content-Type": "application/json", **bearer_headers(token)},
        json=payload,
        timeout=20,
    )

    # Jira often returns 204 No Content on success
    if resp.status_code in (200, 204):
        return {"ok": True, "status": resp.status_code}

    try:
        msg = resp.json()
    except Exception:
        msg = resp.text
    raise RuntimeError(f"Assign failed [{resp.status_code}]: {msg}")


def unassign_issue(
    issue_key: str,
    base_url_override: Optional[str] = None,
    token_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unassign an issue.
    Jira API v2: PUT /issue/{key}/assignee with {"name": None} (or {"accountId": None})
    """
    base_url = (base_url_override or get_base_url())
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    url = f"{base_url.rstrip('/')}/rest/api/2/issue/{issue_key}/assignee"
    payload = {"name": None}  # works for Server/DC; Cloud also accepts {"accountId": None}

    resp = requests.put(
        url,
        headers={"Accept": "application/json", "Content-Type": "application/json", **bearer_headers(token)},
        json=payload,
        timeout=20,
    )

    if resp.status_code in (200, 204):
        return {"ok": True, "status": resp.status_code}

    try:
        msg = resp.json()
    except Exception:
        msg = resp.text
    raise RuntimeError(f"Unassign failed [{resp.status_code}]: {msg}")

def find_user(
    query: str,
    base_url_override: Optional[str] = None,
    token_override: Optional[str] = None,
) -> list[dict]:
    """
    Search Jira users by email, display name, or username.
    Auto-detects whether to use `query` (Cloud/new DC) or `username` (older Server/DC).
    """
    base_url = (base_url_override or get_base_url())
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    search_url = f"{base_url.rstrip('/')}/rest/api/2/user/search"

    # Try Cloud/new DC style first
    for params in ({"query": query, "maxResults": 20}, {"username": query, "maxResults": 20}):
        resp = requests.get(
            search_url,
            headers={"Accept": "application/json", **bearer_headers(token)},
            params=params,
            timeout=20,
        )
        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception as e:
                raise RuntimeError(f"Failed to parse user search JSON: {e}")
        elif resp.status_code == 400 and "username" in resp.text.lower():
            # Try next param style
            continue
        else:
            try:
                msg = resp.json()
            except Exception:
                msg = resp.text
            raise RuntimeError(f"User search failed [{resp.status_code}]: {msg}")

    return []

def get_transitions(issue_key, base_url_override=None, token_override=None):
    base_url = base_url_override or get_base_url()
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    url = f"{base_url.rstrip('/')}/rest/api/2/issue/{issue_key}/transitions"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=20
    )
    resp.raise_for_status()
    return resp.json().get("transitions", [])

def transition_issue(issue_key, transition_id, base_url_override=None, token_override=None):
    base_url = base_url_override or get_base_url()
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    url = f"{base_url.rstrip('/')}/rest/api/2/issue/{issue_key}/transitions"
    payload = {"transition": {"id": transition_id}}
    resp = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        timeout=20
    )
    resp.raise_for_status()
    return resp.json() if resp.text else {"ok": True}

def attach_files(
    issue_key: str,
    paths: list[str],
    base_url_override: Optional[str] = None,
    token_override: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Upload one or more files to an issue.
    Jira: POST /rest/api/2/issue/{key}/attachments
    Requires header: X-Atlassian-Token: no-check
    Returns a list of attachment metadata dicts.
    """
    base_url = (base_url_override or get_base_url())
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    url = f"{base_url.rstrip('/')}/rest/api/2/issue/{issue_key}/attachments"

    # prepare files; keep file handles open until request completes
    to_close = []
    files = []
    try:
        for p in paths:
            if not os.path.isfile(p):
                raise RuntimeError(f"File not found: {p}")
            fh = open(p, "rb")
            to_close.append(fh)
            files.append(("file", (os.path.basename(p), fh, "application/octet-stream")))

        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "X-Atlassian-Token": "no-check",  # required by Jira for attachments
            },
            files=files,  # requests sets proper multipart Content-Type
            timeout=60,
        )
        # Jira returns 200 and a JSON array of attachments
        if resp.status_code not in (200, 201):
            try:
                msg = resp.json()
            except Exception:
                msg = resp.text
            raise RuntimeError(f"Attachment upload failed [{resp.status_code}]: {msg}")

        try:
            return resp.json()  # list[dict]
        except Exception as e:
            raise RuntimeError(f"Failed to parse attachment response JSON: {e}")
    finally:
        for fh in to_close:
            try: fh.close()
            except Exception: pass

def get_issue(
    issue_key: str,
    base_url_override: Optional[str] = None,
    token_override: Optional[str] = None,
    expand: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Fetch a full Jira issue with optional expand fields (e.g., ["renderedFields","names","transitions"]).
    Returns the raw JSON.
    """
    base_url = base_url_override or get_base_url()
    if not base_url:
        raise RuntimeError("No base URL configured. Run: cashout auth login")

    token = get_token(base_url, token_override)
    if not token:
        raise RuntimeError("No token available. Run: cashout auth login")

    url = f"{base_url.rstrip('/')}/rest/api/2/issue/{issue_key}"
    params = {}
    if expand:
        params["expand"] = ",".join(expand)

    resp = requests.get(
        url,
        headers={"Accept": "application/json", **bearer_headers(token)},
        params=params,
        timeout=30,
    )
    if resp.status_code != 200:
        try:
            msg = resp.json()
        except Exception:
            msg = resp.text
        raise RuntimeError(f"Issue fetch failed [{resp.status_code}]: {msg}")

    return resp.json()
