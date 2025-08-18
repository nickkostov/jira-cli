# jira — Jira (Bearer) CLI

Create Jira tickets, add comments, and list issues from your terminal using a **Bearer token**.  
No git actions yet (that can be added later).

---

## Features (current)

- **Auth**
  - `jira auth login` — store **base URL** and **Bearer token** (token saved to OS keychain via `keyring`)
  - `jira auth whoami` — verify token against `/rest/api/2/myself`
  - `jira auth logout` — clear stored token for the current base URL
- **Tickets**
  - `jira ticket create` — create an issue (`Task`, `Bug`, `Story`, `Spike`)
  - `jira ticket comment` — add a comment to an issue (inline or via `$EDITOR`)
  - `jira ticket list` — list issues (open by default), with filters and JSON output

---

## Install

> Requires Python 3.9+

From the project root (where `pyproject.toml` / `setup.cfg` live):

    pip install -e .          # dev install
    # or:
    pipx install .            # global user install (recommended)

Dependencies you may want:

    pip install keyring click requests

---

## Quick start

1) **Login**

    jira auth login
    # Base URL: https://jira.yourdomain.com
    # Token: **** (paste your PAT / Bearer token)

This stores:
- **Base URL** in: `~/.config/jira/config.json` (or `$XDG_CONFIG_HOME/jira/config.json`)
- **Token** in your **OS keychain** under service `jira-bearer` (if `keyring` is installed)

2) **Create a ticket**

    jira ticket create
    # prompts for: Project, Summary
    # optional flags: --type, --desc, --label, --priority

3) **Comment on a ticket**

    jira ticket comment PP-123 -b "Deployed to staging."
    # or open $EDITOR for multi-line:
    jira ticket comment PP-123

4) **List open tickets in a project**

    jira ticket list -p PP
    # mine only:
    jira ticket list -p PP --mine
    # include Done/Closed:
    jira ticket list -p PP --all
    # with extra JQL:
    jira ticket list -p PP --jql 'labels = pp-transaction-consumer'
    # JSON output:
    jira ticket list -p PP -n 20 --json

---

## Command reference

### Auth

    jira auth login
        # prompts for base URL & token and validates them

    jira auth whoami
        # shows current base URL and validates token via /rest/api/2/myself

    jira auth logout
        # clears saved token for the current base URL

### Tickets

    jira ticket create
        -p, --project       Project key (prompted if omitted)
        -t, --type          Task | Bug | Story | Spike  (default: Task)
        -s, --summary       Issue title (prompted if omitted)
        -d, --desc          Issue description
        -l, --label         Repeatable label flag (e.g., -l foo -l bar)
        --priority          Priority name (e.g., Highest, High, Normal, Low)
        --base-url          Override saved base URL
        --token             Override stored Bearer token
        --json              Print raw JSON response

    jira ticket comment ISSUE-KEY
        -b, --body          Comment text (or omit to open $EDITOR)
        --base-url          Override saved base URL
        --token             Override stored Bearer token

    jira ticket list
        -p, --project       Project key (prompted if omitted)
        --all               Include Done/


# Assign by email (auto-resolves to accountId or username)
jira ticket assign PP-123 --email svetoslav.nenov@weareplanet.com

# If multiple matches, pick the first automatically
jira ticket assign PP-123 --email "svetoslav" --first

# Explicit (still supported)
jira ticket assign PP-123 --account-id 557058:abcd-1234-...
jira ticket assign PP-123 --user svetoslav.nenov

# Assign by account ID (Cloud/DC, most reliable)
jira ticket assign PP-123 --account-id 557058:abcd-1234-5678-...

# Assign by username (Server/DC)
jira ticket assign PP-123 --user svetoslav.nenov

# Assign by email (auto-resolves to accountId or username)
jira ticket assign PP-123 --email svetoslav.nenov@weareplanet.com

# Assign by email when multiple matches exist
jira ticket assign PP-123 --email "svetoslav" --first

# Open an issue in your default browser
jira ticket open PP-123

# Just print the URL (don’t open)
jira ticket open PP-123 --print-only

# Skip server validation (faster, works without token)
jira ticket open PP-123 --no-validate

# Force a specific browser (falls back to default if missing)
jira ticket open PP-123 --browser chrome

# Using a different base URL or token just for this call
jira ticket open PP-123 --base-url https://jira.weareplanet.com --token "$JIRA_BEARER_TOKEN"
