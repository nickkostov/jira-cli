#!/usr/bin/env python3
# src/cashout/cli.py
from __future__ import annotations

import os
import json
from datetime import datetime
import click

from .auth import auth as auth_group, get_base_url
from .issue import create_issue_simple, add_comment, search_issues, assign_issue, unassign_issue, find_user

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
@click.option("--jql", "jql_extra", help="Extra JQL to AND onto the base query.")
@click.option("-n", "--limit", type=int, default=50, show_default=True, help="Max issues to return.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.option("--base-url", help="Override saved base URL.")
@click.option("--token", help="Override stored Bearer token.")
def ticket_list(project, all_statuses, mine, assignee, jql_extra, limit, as_json, base_url, token):
    """
    List tickets in a project (defaults to open only).
    """
    try:
        data = search_issues(
            project_key=project,
            jql_extra=jql_extra,
            only_open=not all_statuses,
            assignee=None if mine else assignee,
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

    if as_json:
        click.echo(json.dumps(data, indent=2))
        return

    if not issues:
        click.secho("No issues found.", fg="yellow")
        return

    def pick(field, dct, default=""):
        val = (dct or {}).get(field, default)
        return default if val is None else val

    rows = []
    for it in issues:
        key = it.get("key", "")
        f = it.get("fields", {}) or {}

        summary = pick("summary", f, "")
        issuetype = (pick("issuetype", f, {}) or {}).get("name", "")
        status = (pick("status", f, {}) or {}).get("name", "")
        prio = (pick("priority", f, {}) or {}).get("name", "")

        assg = pick("assignee", f, {}) or {}
        assignee_name = assg.get("displayName") or assg.get("name") or ""

        updated_raw = pick("updated", f, "")
        try:
            updated = datetime.fromisoformat(updated_raw.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except Exception:
            updated = updated_raw or ""

        rows.append((key, issuetype, status, prio, assignee_name, updated, summary))

    def trunc(s, n):
        return s if len(s) <= n else s[: n - 1] + "…"

    widths = {
        "key": 11,
        "type": 8,
        "status": 12,
        "prio": 8,
        "assignee": 18,
        "updated": 16,
    }

    header = f"{'KEY':<{widths['key']}}  {'TYPE':<{widths['type']}}  {'STATUS':<{widths['status']}}  {'PRIORITY':<{widths['prio']}}  {'ASSIGNEE':<{widths['assignee']}}  {'UPDATED':<{widths['updated']}}  SUMMARY"
    click.secho(header, fg="cyan")
    click.secho("-" * len(header), dim=True)

    for key, itype, status, prio, assignee_name, updated, summary in rows:
        line = (
            f"{trunc(key, widths['key']):<{widths['key']}}  "
            f"{trunc(itype, widths['type']):<{widths['type']}}  "
            f"{trunc(status, widths['status']):<{widths['status']}}  "
            f"{trunc(prio, widths['prio']):<{widths['prio']}}  "
            f"{trunc(assignee_name, widths['assignee']):<{widths['assignee']}}  "
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


if __name__ == "__main__":
    cli()
