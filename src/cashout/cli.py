#!/usr/bin/env python3
# src/cashout/cli.py
from __future__ import annotations
from .issue import transition_issue, get_transitions
from datetime import datetime

import os
import json
import click
import requests

from .auth import auth as auth_group, get_base_url, get_token
from .issue import (
    create_issue_simple,
    add_comment,
    search_issues,
    assign_issue,
    unassign_issue,
    find_user,
    attach_files,
    get_issue
)

from .open import open_issue


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    """cashout CLI — Jira (Bearer token) utilities."""
    pass


# -----------------------------
# Subcommands: auth
# -----------------------------
cli.add_command(auth_group, name="auth")


# -----------------------------
# Subcommands: ticket
# -----------------------------
@cli.group(help="Work with Jira tickets.")
def ticket():
    pass


@ticket.command("create")
@click.option("-p", "--project", prompt=True, help="Project key (e.g., APP, PP).")
@click.option(
    "-t", "--type", "issue_type",
    default="Task", show_default=True,
    type=click.Choice(["Task", "Bug", "Story", "Spike"], case_sensitive=False),
    help="Issue type name."
)
@click.option("-s", "--summary", prompt=True, help="Issue summary/title.")
@click.option("-d", "--desc", "description", help="Issue description.")
@click.option("-l", "--label", "labels", multiple=True, help="Add label(s). Repeatable.")
@click.option("--priority", help="Priority name (e.g., Highest, High, Normal, Low).")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON response.")
def ticket_create(project, issue_type, summary, description, labels, priority, base_url, token, as_json):
    """
    Create a Jira ticket using Bearer token auth and print the new key & URL.
    """
    try:
        data = create_issue_simple(
            project_key=project,
            summary=summary,
            issue_type=issue_type,
            description=description,
            labels=list(labels),
            priority=priority,
            base_url_override=base_url,
            token_override=token,
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    if as_json:
        click.echo(json.dumps(data, indent=2))
        return

    key = data.get("key")
    if not key:
        click.secho(f"Unexpected response: {data}", fg="yellow")
        return

    click.secho(f"Created: {key}", fg="green")
    bu = base_url or os.getenv("JIRA_BASE_URL") or get_base_url()
    if bu:
        click.echo(f"{bu.rstrip('/')}/browse/{key}")


@ticket.command("comment")
@click.argument("issue_key", required=True)
@click.option("-b", "--body", "comment_body", help="Comment text. If omitted, opens your $EDITOR.")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
def ticket_comment(issue_key, comment_body, base_url, token):
    """
    Add a comment to an existing Jira ticket.
    """
    if not comment_body:
        template = "\n# Write your comment above. Lines starting with # are ignored.\n"
        edited = click.edit(template)
        if not edited:
            click.secho("Aborted: no comment provided.", fg="yellow")
            return
        comment_body = "\n".join(
            line for line in edited.splitlines() if not line.strip().startswith("#")
        ).strip()
        if not comment_body:
            click.secho("Aborted: comment is empty after stripping comments.", fg="yellow")
            return

    try:
        data = add_comment(
            issue_key=issue_key,
            comment_body=comment_body,
            base_url_override=base_url,
            token_override=token,
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    cid = data.get("id")
    click.secho(f"Comment {cid} added to {issue_key}", fg="green")

@ticket.command("list")
@click.option("-p", "--project", prompt=True, help="Project key (e.g., APP, PP).")
@click.option("--all", "all_statuses", is_flag=True, help="Include Done/Closed issues (default: open only).")
@click.option("--mine", is_flag=True, help="Only issues assigned to you.")
@click.option("--assignee", help='Filter by assignee (username/email). Ignored if --mine is set.')
@click.option("--assigned", is_flag=True, help="Only issues with an assignee.")
@click.option("--unassigned", is_flag=True, help="Only issues with no assignee.")
@click.option("--jql", "jql_extra", help="Extra JQL to AND onto the base query.")
@click.option("-n", "--limit", type=int, default=50, show_default=True, help="Max issues to return.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.option("--csv", "as_csv", is_flag=True, help="Output CSV instead of table.")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
def ticket_list(project, all_statuses, mine, assignee, assigned, unassigned, jql_extra, limit, as_json, as_csv, base_url, token):
    """
    List tickets in a project (defaults to open only).
    """
    # Mutually exclusive: --mine / --assignee / --assigned / --unassigned
    if sum(bool(x) for x in (mine, bool(assignee), assigned, unassigned)) > 1:
        click.secho("Use only one of: --mine, --assignee, --assigned, or --unassigned.", fg="red", err=True)
        raise SystemExit(1)

    # Build final JQL with optional assignment clauses
    final_jql = jql_extra or ""
    if assigned:
        clause = "assignee is not EMPTY"
        final_jql = f"{final_jql} AND {clause}" if final_jql else clause
    elif unassigned:
        clause = "assignee is EMPTY"
        final_jql = f"{final_jql} AND {clause}" if final_jql else clause

    try:
        data = search_issues(
            project_key=project,
            jql_extra=final_jql,
            only_open=not all_statuses,
            assignee=None if (mine or assigned or unassigned) else assignee,
            mine=mine,
            limit=limit,
            base_url_override=base_url,
            token_override=token,
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    issues = data.get("issues", [])
    total = data.get("total", 0)

    # Raw JSON output
    if as_json:
        click.echo(json.dumps(data, indent=2))
        return

    # CSV output
    if as_csv:
        import csv, sys
        writer = csv.writer(sys.stdout)
        writer.writerow(["KEY", "TYPE", "STATUS", "PRIORITY", "ASSIGNEE", "UPDATED", "SUMMARY"])
        for it in issues:
            f = (it.get("fields") or {})
            assg = f.get("assignee") or {}
            updated_raw = f.get("updated", "")
            try:
                updated = datetime.fromisoformat(updated_raw.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
            except Exception:
                updated = updated_raw or ""
            writer.writerow([
                it.get("key", "") or "",
                (f.get("issuetype") or {}).get("name", "") or "",
                (f.get("status") or {}).get("name", "") or "",
                (f.get("priority") or {}).get("name", "") or "",
                assg.get("displayName") or assg.get("name") or "",
                updated,
                f.get("summary", "") or "",
            ])
        return

    if not issues:
        click.secho("No issues found.", fg="yellow")
        return

    # Helpers
    def pick(field, dct, default=""):
        val = (dct or {}).get(field, default)
        return default if val is None else val

    def trunc(s, n):
        return s if len(s) <= n else s[: n - 1] + "…"

    # Build rows
    rows = []
    for it in issues:
        key = it.get("key", "") or ""
        f = it.get("fields", {}) or {}
        summary   = pick("summary", f, "")
        issuetype = (pick("issuetype", f, {}) or {}).get("name", "") or ""
        status    = (pick("status",    f, {}) or {}).get("name", "") or ""
        prio      = (pick("priority",  f, {}) or {}).get("name", "") or ""
        assg      = pick("assignee", f, {}) or {}
        assignee_name = assg.get("displayName") or assg.get("name") or ""
        updated_raw = pick("updated", f, "")
        try:
            updated = datetime.fromisoformat(updated_raw.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except Exception:
            updated = updated_raw or ""
        rows.append((key, issuetype, status, prio, assignee_name, updated, summary))

    # Table widths and header
    widths = {"key": 11, "type": 8, "status": 12, "prio": 8, "assignee": 18, "updated": 16}
    header = f"{'KEY':<{widths['key']}}  {'TYPE':<{widths['type']}}  {'STATUS':<{widths['status']}}  {'PRIORITY':<{widths['prio']}}  {'ASSIGNEE':<{widths['assignee']}}  {'UPDATED':<{widths['updated']}}  SUMMARY"
    click.secho(header, fg="cyan")
    click.secho("-" * len(header), dim=True)

    # Print colored rows (yellow unassigned, blue assigned)
    for key, itype, status, prio, assignee_name, updated, summary in rows:
        plain_assignee = assignee_name.strip() or "(unassigned)"
        plain_trunc = trunc(plain_assignee, widths["assignee"])
        colored = click.style(plain_trunc, fg="yellow" if plain_assignee == "(unassigned)" else "blue")
        pad = " " * (widths["assignee"] - len(plain_trunc))

        line = (
            f"{trunc(key, widths['key']):<{widths['key']}}  "
            f"{trunc(itype, widths['type']):<{widths['type']}}  "
            f"{trunc(status, widths['status']):<{widths['status']}}  "
            f"{trunc(prio, widths['prio']):<{widths['prio']}}  "
            f"{colored}{pad}  "
            f"{trunc(updated, widths['updated']):<{widths['updated']}}  "
            f"{summary}"
        )
        click.echo(line)

    click.secho(f"\nShowing {len(issues)} of ~{total} matching issues.", dim=True)



@ticket.command("assign")
@click.argument("issue_key", required=True)
@click.option("--email", help="User email (resolve to accountId/username automatically).")
@click.option("--user", help="Jira username (Server/DC). Mutually exclusive with --account-id and --email.")
@click.option("--account-id", help="Jira accountId (Cloud/DC). Takes precedence over --user if both supplied.")
@click.option("--first", is_flag=True, help="When --email matches multiple users, pick the first automatically.")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
def ticket_assign(issue_key, email, user, account_id, first, base_url, token):
    """
    Assign ISSUE-KEY to a user.

    Priority order:
      --account-id > --user > --email (resolved).
    """
    resolved_account_id = account_id
    resolved_user = user

    if email and (account_id or user):
        click.secho("Use only one of --email / --user / --account-id.", fg="red", err=True)
        raise SystemExit(1)

    if email:
        try:
            candidates = find_user(email, base_url_override=base_url, token_override=token)
        except Exception as e:
            click.secho(f"User lookup failed: {e}", fg="red", err=True)
            raise SystemExit(1)

        if not candidates:
            click.secho(f"No users found for '{email}'.", fg="yellow")
            raise SystemExit(1)

        # Prefer exact email match when present
        exact = [u for u in candidates if (u.get("emailAddress") or "").lower() == email.lower()]
        if len(exact) == 1:
            resolved_account_id = exact[0].get("accountId")
            resolved_user = exact[0].get("name")
        elif len(exact) > 1 and not first:
            click.secho(f"Multiple exact matches for {email}. Specify --account-id or pass --first.", fg="yellow")
            header = f"{'ACCOUNT ID':<40}  {'USERNAME':<20}  {'DISPLAY NAME':<30}  EMAIL"
            click.secho(header, fg="cyan"); click.secho("-" * len(header), dim=True)
            for u in exact:
                click.echo(f"{(u.get('accountId') or ''):<40}  {(u.get('name') or ''):<20}  {(u.get('displayName') or ''):<30}  {(u.get('emailAddress') or '')}")
            raise SystemExit(1)
        else:
            if len(candidates) == 1 or first:
                chosen = candidates[0]
                resolved_account_id = chosen.get("accountId")
                resolved_user = chosen.get("name")
            else:
                click.secho(f"Multiple users matched '{email}'. Refine query or pass --first.", fg="yellow")
                header = f"{'ACCOUNT ID':<40}  {'USERNAME':<20}  {'DISPLAY NAME':<30}  EMAIL"
                click.secho(header, fg="cyan"); click.secho("-" * len(header), dim=True)
                for u in candidates:
                    click.echo(f"{(u.get('accountId') or ''):<40}  {(u.get('name') or ''):<20}  {(u.get('displayName') or ''):<30}  {(u.get('emailAddress') or '')}")
                raise SystemExit(1)

    if not resolved_account_id and not resolved_user:
        click.secho("Provide one of: --email, --account-id, or --user.", fg="red", err=True)
        raise SystemExit(1)

    try:
        assign_issue(
            issue_key=issue_key,
            user=None if resolved_account_id else resolved_user,
            account_id=resolved_account_id,
            base_url_override=base_url,
            token_override=token,
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    who = resolved_account_id or resolved_user or email
    click.secho(f"Assigned {issue_key} → {who}", fg="green")


@ticket.command("unassign")
@click.argument("issue_key", required=True)
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
def ticket_unassign(issue_key, base_url, token):
    """
    Remove assignee from ISSUE-KEY.
    """
    try:
        unassign_issue(
            issue_key=issue_key,
            base_url_override=base_url,
            token_override=token,
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    click.secho(f"Unassigned {issue_key}", fg="green")


@ticket.command("whois")
@click.argument("query", required=True)
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
def ticket_whois(query, base_url, token):
    """
    Search Jira users by email, display name, or username.
    Shows accountId (Cloud) and username (Server/DC).
    """
    try:
        users = find_user(query, base_url_override=base_url, token_override=token)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    if not users:
        click.secho("No matching users found.", fg="yellow")
        return

    header = f"{'ACCOUNT ID':<40}  {'USERNAME':<20}  {'DISPLAY NAME':<30}  EMAIL"
    click.secho(header, fg="cyan")
    click.secho("-" * len(header), dim=True)

    for u in users:
        account_id = u.get("accountId", "") or ""
        username = u.get("name", "") or ""
        display_name = u.get("displayName", "") or ""
        email = u.get("emailAddress", "") or ""
        click.echo(f"{account_id:<40}  {username:<20}  {display_name:<30}  {email}")


@ticket.command("open")
@click.argument("issue_key", required=True)
@click.option("--no-validate", is_flag=True, help="Do not call Jira to validate the issue exists.")
@click.option("--browser", help='Browser to use (e.g., "chrome", "firefox", "safari"). Falls back to default.')
@click.option("--print-only", is_flag=True, help="Print the URL but do not open a browser.")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token (used only when validating).")
def ticket_open(issue_key, no_validate, browser, print_only, base_url, token):
    """
    Open ISSUE-KEY in your web browser.
    """
    try:
        url = open_issue(
            issue_key,
            base_url_override=base_url,
            token_override=token,
            validate=not no_validate,
            browser=browser,
            print_only=print_only,
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    click.echo(url)

@ticket.command("transition")
@click.argument("issue_key", required=True)
@click.option("--to", "status_name", required=True, help="Destination status name (e.g., 'In Progress').")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
def ticket_transition(issue_key, status_name, base_url, token):
    """
    Change the status of a ticket to a given workflow transition name.
    """
    try:
        transitions = get_transitions(
            issue_key=issue_key,
            base_url_override=base_url,
            token_override=token
        )
    except Exception as e:
        click.secho(f"Error fetching transitions: {e}", fg="red", err=True)
        raise SystemExit(1)

    if not transitions:
        click.secho("No transitions available for this issue.", fg="yellow")
        return

    # Try to find matching transition
    match = None
    for t in transitions:
        if t.get("name", "").lower() == status_name.lower():
            match = t
            break

    if not match:
        click.secho(f"Status '{status_name}' not found. Available:", fg="yellow")
        for t in transitions:
            click.echo(f"- {t.get('name')}")
        return

    try:
        transition_issue(
            issue_key=issue_key,
            transition_id=match.get("id"),
            base_url_override=base_url,
            token_override=token
        )
    except Exception as e:
        click.secho(f"Error transitioning issue: {e}", fg="red", err=True)
        raise SystemExit(1)

    click.secho(f"✅ {issue_key} transitioned to '{status_name}'", fg="green")

@ticket.command("assign")
@click.argument("issue_key", required=True)
@click.option("--me", is_flag=True, help="Assign to yourself.")
@click.option("--email", help="User email (resolve to accountId/username automatically).")
@click.option("--user", help="Jira username (Server/DC). Mutually exclusive with --account-id and --email.")
@click.option("--account-id", help="Jira accountId (Cloud/DC). Takes precedence over --user if both supplied.")
@click.option("--first", is_flag=True, help="When --email matches multiple users, pick the first automatically.")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
def ticket_assign(issue_key, me, email, user, account_id, first, base_url, token):
    """
    Assign ISSUE-KEY to a user.

    Priority order:
      --me > --account-id > --user > --email (resolved).
    """
    resolved_account_id = account_id
    resolved_user = user

    if sum(bool(x) for x in (me, bool(email), bool(user), bool(account_id))) > 1:
        click.secho("Use only one of: --me, --email, --user, or --account-id.", fg="red", err=True)
        raise SystemExit(1)

    if me:
        base_url_f = base_url or get_base_url()
        if not base_url_f:
            click.secho("No base URL configured. Run: cashout auth login", fg="red", err=True)
            raise SystemExit(1)

        try:
            token_f = get_token(base_url_f, token)
        except Exception as e:
            click.secho(f"Token error: {e}", fg="red", err=True)
            raise SystemExit(1)

        if not token_f:
            click.secho("No token available. Run: cashout auth login", fg="red", err=True)
            raise SystemExit(1)

        try:
            resp = requests.get(
                f"{base_url_f.rstrip('/')}/rest/api/2/myself",
                headers={"Authorization": f"Bearer {token_f}", "Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            click.secho(f"Failed to resolve current user via /myself: {e}", fg="red", err=True)
            raise SystemExit(1)

        me_data = resp.json() or {}
        resolved_account_id = me_data.get("accountId")
        resolved_user = me_data.get("name")


    elif email:
        try:
            candidates = find_user(email, base_url_override=base_url, token_override=token)
        except Exception as e:
            click.secho(f"User lookup failed: {e}", fg="red", err=True)
            raise SystemExit(1)

        if not candidates:
            click.secho(f"No users found for '{email}'.", fg="yellow")
            raise SystemExit(1)

        exact = [u for u in candidates if (u.get("emailAddress") or "").lower() == email.lower()]
        if len(exact) == 1:
            resolved_account_id = exact[0].get("accountId")
            resolved_user = exact[0].get("name")
        elif len(exact) > 1 and not first:
            click.secho(f"Multiple exact matches for {email}. Specify --account-id or pass --first.", fg="yellow")
            raise SystemExit(1)
        else:
            chosen = candidates[0]
            resolved_account_id = chosen.get("accountId")
            resolved_user = chosen.get("name")

    if not resolved_account_id and not resolved_user:
        click.secho("Provide one of: --me, --email, --account-id, or --user.", fg="red", err=True)
        raise SystemExit(1)

    try:
        assign_issue(
            issue_key=issue_key,
            user=None if resolved_account_id else resolved_user,
            account_id=resolved_account_id,
            base_url_override=base_url,
            token_override=token,
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    who = resolved_account_id or resolved_user or "me"
    click.secho(f"Assigned {issue_key} → {who}", fg="green")

@ticket.command("attach")
@click.argument("issue_key", required=True)
@click.argument("files", nargs=-1, required=True, metavar="FILE...")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
def ticket_attach(issue_key, files, base_url, token):
    """
    Attach one or more files to ISSUE-KEY.

    Example:
      cashout ticket attach PP-123 ./file.log ./screenshot.png
    """
    # de-dup & normalize
    paths = [os.path.expanduser(p) for p in files]
    try:
        meta_list = attach_files(
            issue_key=issue_key,
            paths=paths,
            base_url_override=base_url,
            token_override=token,
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    if not meta_list:
        click.secho("No attachments uploaded.", fg="yellow")
        return

    # Pretty print a small table
    header = f"{'ID':<10}  {'FILENAME':<30}  {'SIZE(B)':<12}  AUTHOR"
    click.secho(header, fg="cyan")
    click.secho("-" * len(header), dim=True)

    for m in meta_list:
        aid = str(m.get("id", ""))
        name = m.get("filename", "")
        size = str(m.get("size", ""))
        author = (m.get("author") or {}).get("displayName") or (m.get("author") or {}).get("name") or ""
        # truncate filename to keep tidy
        name_short = name if len(name) <= 30 else name[:29] + "…"
        click.echo(f"{aid:<10}  {name_short:<30}  {size:<12}  {author}")

    click.secho(f"\nUploaded {len(meta_list)} attachment(s) to {issue_key}.", fg="green")

@ticket.command("show")
@click.argument("issue_key", required=True)
@click.option("--comments", type=int, default=3, show_default=True,
              help="Number of most recent comments to show.")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def ticket_show(issue_key, comments, base_url, token, as_json):
    """
    Show key fields, description, and recent comments for an issue.
    """
    try:
        issue = get_issue(
            issue_key=issue_key,
            base_url_override=base_url,
            token_override=token,
            expand=["renderedFields", "names", "transitions", "changelog"]
        )
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1)

    if as_json:
        click.echo(json.dumps(issue, indent=2))
        return

    f = issue.get("fields", {}) or {}
    key = issue.get("key", issue_key)
    summary = f.get("summary", "")
    status = (f.get("status") or {}).get("name", "")
    issue_type = (f.get("issuetype") or {}).get("name", "")
    priority = (f.get("priority") or {}).get("name", "")
    reporter = (f.get("reporter") or {}).get("displayName", "")
    assignee = (f.get("assignee") or {}).get("displayName", "") or "Unassigned"
    created = f.get("created", "")
    updated = f.get("updated", "")
    description = f.get("description", "")

    # --- Handle Jira description formats (string or ADF dict) ---
    def _adf_to_text(node) -> str:
        # Minimal ADF → text: recursively gather text from content nodes
        if isinstance(node, dict):
            t = node.get("type")
            if t == "text":
                return node.get("text", "")
            parts = []
            for child in (node.get("content") or []):
                parts.append(_adf_to_text(child))
            # Add newlines for block-level nodes
            if t in {"paragraph", "bulletList", "orderedList", "heading", "blockquote"}:
                return "".join(parts) + ("\n" if parts else "")
            return "".join(parts)
        elif isinstance(node, list):
            return "".join(_adf_to_text(c) for c in node)
        return ""

    if isinstance(description, dict):  # likely ADF
        description_text = _adf_to_text(description).strip()
    else:
        description_text = (description or "").strip()

    # Pretty truncate super long descriptions (so terminals survive)
    max_desc_len = 1200
    desc_shown = description_text[:max_desc_len].rstrip()
    if len(description_text) > max_desc_len:
        desc_shown += "\n…(truncated)"

    # --- Color coding ---
    status_color = "green" if status.lower() == "done" else "cyan"
    assignee_color = "yellow" if assignee == "Unassigned" else "blue"

    # --- Big subject ---
    click.secho(f"[{key}] {summary}", fg="cyan", bold=True)
    click.echo()
    click.echo(f"Type: {issue_type}")
    click.secho(f"Status: {status}", fg=status_color)
    click.echo(f"Priority: {priority}")
    click.echo(f"Reporter: {reporter}")
    click.secho(f"Assignee: {assignee}", fg=assignee_color)
    click.echo(f"Created: {created}")
    click.echo(f"Updated: {updated}")

    # --- Description ---
    click.secho("\nDescription:", fg="magenta")
    if desc_shown:
        click.echo(desc_shown)
    else:
        click.secho("(no description)", dim=True)

    # --- Comments ---
    comments_list = (f.get("comment") or {}).get("comments", [])
    if comments_list:
        click.secho(f"\nLast {min(comments, len(comments_list))} comment(s):", fg="yellow")
        for c in sorted(comments_list, key=lambda x: x.get("created", ""), reverse=True)[:comments]:
            author = (c.get("author") or {}).get("displayName", "Unknown")
            body = (c.get("body") or "").strip()
            created_at = c.get("created", "")
            click.secho(f"\n[{author} @ {created_at}]", fg="green")
            click.echo(body)
    else:
        click.secho("\nNo comments found.", dim=True)


if __name__ == "__main__":
    cli()
