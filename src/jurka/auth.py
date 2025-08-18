#!/usr/bin/env python3
# src/jira/auth.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import click
import requests

# Optional secure storage for the token
try:
    import keyring  # pip install keyring
except Exception:  # pragma: no cover
    keyring = None  # type: ignore

CONFIG_DIR = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "jira"
CONFIG_PATH = CONFIG_DIR / "config.json"
KEYRING_SERVICE = "jira-bearer"


# -----------------------------
# File config (non-sensitive)
# -----------------------------
def _read_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {}

def _write_config(cfg: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

def get_base_url() -> Optional[str]:
    saved = _read_config()
    return os.getenv("JIRA_BASE_URL") or saved.get("base_url")

def set_base_url(base_url: str) -> None:
    cfg = _read_config()
    cfg["base_url"] = base_url.rstrip("/")
    _write_config(cfg)


# -----------------------------
# Token (sensitive)
# -----------------------------
def _keyring_available() -> bool:
    return keyring is not None

def get_token(base_url: Optional[str], explicit_token: Optional[str] = None) -> Optional[str]:
    """Return token preference: explicit > keyring > env var."""
    if explicit_token:
        return explicit_token
    if base_url and _keyring_available():
        try:
            return keyring.get_password(KEYRING_SERVICE, base_url)  # type: ignore[attr-defined]
        except Exception:
            pass
    return os.getenv("JIRA_BEARER_TOKEN")

def set_token(base_url: str, token: str) -> None:
    if not _keyring_available():
        click.secho(
            "Warning: `keyring` not available; token NOT stored. Install with: pip install keyring",
            fg="yellow",
        )
        return
    try:
        keyring.set_password(KEYRING_SERVICE, base_url, token)  # type: ignore[attr-defined]
    except Exception as e:
        click.secho(f"Failed to store token in keyring: {e}", fg="red", err=True)

def clear_token(base_url: str) -> None:
    if not _keyring_available():
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, base_url)  # type: ignore[attr-defined]
    except Exception:
        pass


# -----------------------------
# HTTP helpers
# -----------------------------
def bearer_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def validate_token(base_url: str, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Calls Jira /rest/api/2/myself to verify the Bearer token.
    Returns (ok, payload). ok=False if non-2xx or error.
    """
    url = f"{base_url.rstrip('/')}/rest/api/2/myself"
    try:
        resp = requests.get(url, headers=bearer_headers(token), timeout=20)
    except requests.RequestException as e:
        return False, {"error": str(e)}
    if resp.status_code >= 300:
        try:
            return False, resp.json()
        except Exception:
            return False, {"status": resp.status_code, "text": resp.text}
    try:
        return True, resp.json()
    except Exception:
        return True, None


# -----------------------------
# Click commands (auth group)
# -----------------------------
@click.group(help="Authentication commands for jira.")
def auth() -> None:
    pass

@auth.command("login")
@click.option("--base-url", prompt=True, help="Jira base URL (e.g., https://jira.example.com)")
@click.option("--token", prompt=True, hide_input=True, confirmation_prompt=True, help="Bearer token / PAT")
def cmd_login(base_url: str, token: str) -> None:
    """Save base URL and Bearer token (token goes to keyring if available)."""
    # save base url
    base_url = base_url.rstrip("/")
    set_base_url(base_url)

    # store token
    set_token(base_url, token)

    # validate
    ok, payload = validate_token(base_url, token)
    if ok:
        display = payload.get("displayName") if isinstance(payload, dict) else None
        acct = payload.get("name") or payload.get("accountId") if isinstance(payload, dict) else None
        click.secho("✅ Login OK.", fg="green")
        if display or acct:
            click.echo(f"User: {display or ''} {f'({acct})' if acct else ''}".strip())
    else:
        click.secho("⚠️  Saved, but token validation FAILED.", fg="yellow")
        if payload:
            click.echo(payload)

@auth.command("whoami", help="Show the current base URL and validate the stored token.")
@click.option("--base-url", help="Override base URL; otherwise use saved/env.")
@click.option("--token", help="Override token; otherwise use keyring/env.")
def cmd_whoami(base_url: Optional[str], token: Optional[str]) -> None:
    base_url = (base_url or get_base_url())
    if not base_url:
        click.secho("No base URL configured. Run: jira auth login", fg="red", err=True)
        raise SystemExit(1)

    tok = get_token(base_url, token)
    if not tok:
        click.secho("No token found. Run: jira auth login", fg="red", err=True)
        raise SystemExit(1)

    ok, payload = validate_token(base_url, tok)
    click.echo(f"Base URL: {base_url}")
    if ok:
        click.secho("Token: OK ✅", fg="green")
        if isinstance(payload, dict):
            display = payload.get("displayName")
            acct = payload.get("name") or payload.get("accountId")
            if display or acct:
                click.echo(f"User: {display or ''} {f'({acct})' if acct else ''}".strip())
    else:
        click.secho("Token: INVALID ❌", fg="red")
        if payload:
            click.echo(payload)

@auth.command("logout", help="Forget the stored token for the current base URL.")
@click.option("--base-url", help="Override base URL; otherwise use saved/env.")
def cmd_logout(base_url: Optional[str]) -> None:
    base_url = (base_url or get_base_url())
    if not base_url:
        click.secho("No base URL configured.", fg="yellow")
        return
    clear_token(base_url)
    click.secho(f"Token cleared for {base_url}", fg="green")
