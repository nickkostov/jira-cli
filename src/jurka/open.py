# src/jira/open.py
from __future__ import annotations

import webbrowser
import requests # type: ignore
from typing import Optional, Dict, Any

from .auth import get_base_url, get_token, bearer_headers


def make_issue_url(base_url: str, issue_key: str) -> str:
    return f"{base_url.rstrip('/')}/browse/{issue_key}"


def _validate_issue_exists(base_url: str, token: str, issue_key: str) -> Dict[str, Any]:
    """
    Minimal validation that an issue exists.
    Returns JSON payload with at least fields.key/fields.summary on success.
    Raises requests.HTTPError on non-2xx.
    """
    url = f"{base_url.rstrip('/')}/rest/api/2/issue/{issue_key}"
    resp = requests.get(url, headers={"Accept": "application/json", **bearer_headers(token)}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def open_issue(
    issue_key: str,
    *,
    base_url_override: Optional[str] = None,
    token_override: Optional[str] = None,
    validate: bool = True,
    browser: Optional[str] = None,
    print_only: bool = False,
) -> str:
    """
    Build the browse URL and (optionally) validate the issue before opening it.

    Returns the URL (always), and opens it in the default browser unless print_only=True.
    """
    base_url = base_url_override or get_base_url()
    if not base_url:
        raise RuntimeError("No base URL configured. Run: jira auth login")

    url = make_issue_url(base_url, issue_key)

    if validate:
        token = get_token(base_url, token_override)
        if not token:
            raise RuntimeError("No token available to validate the issue. Use --no-validate or run: jira auth login")
        # Will raise if invalid
        _validate_issue_exists(base_url, token, issue_key)

    if not print_only:
        if browser:
            try:
                b = webbrowser.get(browser)  # e.g. "chrome", "firefox", "safari"
                b.open(url, new=2)           # new=2 → new tab, if possible
            except webbrowser.Error:
                # Fall back to default browser
                webbrowser.open(url, new=2)
        else:
            webbrowser.open(url, new=2)

    return url
