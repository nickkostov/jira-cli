# cashout — Jira (Bearer) CLI

Create Jira tickets, add comments, and list issues from your terminal using a **Bearer token**.  
No git actions yet (that can be added later).

---

## Features (current)

- **Auth**
  - `cashout auth login` — store **base URL** and **Bearer token** (token saved to OS keychain via `keyring`)
  - `cashout auth whoami` — verify token against `/rest/api/2/myself`
  - `cashout auth logout` — clear stored token for the current base URL
- **Tickets**
  - `cashout ticket create` — create an issue (`Task`, `Bug`, `Story`, `Spike`)
  - `cashout ticket comment` — add a comment to an issue (inline or via `$EDITOR`)
  - `cashout ticket list` — list issues (open by default), with filters and JSON output

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

    cashout auth login
    # Base URL: https://jira.yourdomain.com
    # Token: **** (paste your PAT / Bearer token)

This stores:
- **Base URL** in: `~/.config/cashout/config.json` (or `$XDG_CONFIG_HOME/cashout/config.json`)
- **Token** in your **OS keychain** under service `cashout-bearer` (if `keyring` is installed)

2) **Create a ticket**

    cashout ticket create
    # prompts for: Project, Summary
    # optional flags: --type, --desc, --label, --priority

3) **Comment on a ticket**

    cashout ticket comment PP-123 -b "Deployed to staging."
    # or open $EDITOR for multi-line:
    cashout ticket comment PP-123

4) **List open tickets in a project**

    cashout ticket list -p PP
    # mine only:
    cashout ticket list -p PP --mine
    # include Done/Closed:
    cashout ticket list -p PP --all
    # with extra JQL:
    cashout ticket list -p PP --jql 'labels = pp-transaction-consumer'
    # JSON output:
    cashout ticket list -p PP -n 20 --json

---

## Command reference

### Auth

    cashout auth login
        # prompts for base URL & token and validates them

    cashout auth whoami
        # shows current base URL and validates token via /rest/api/2/myself

    cashout auth logout
        # clears saved token for the current base URL

### Tickets

    cashout ticket create
        -p, --project       Project key (prompted if omitted)
        -t, --type          Task | Bug | Story | Spike  (default: Task)
        -s, --summary       Issue title (prompted if omitted)
        -d, --desc          Issue description
        -l, --label         Repeatable label flag (e.g., -l foo -l bar)
        --priority          Priority name (e.g., Highest, High, Normal, Low)
        --base-url          Override saved base URL
        --token             Override stored Bearer token
        --json              Print raw JSON response

    cashout ticket comment ISSUE-KEY
        -b, --body          Comment text (or omit to open $EDITOR)
        --base-url          Override saved base URL
        --token             Override stored Bearer token

    cashout ticket list
        -p, --project       Project key (prompted if omitted)
        --all               Include Done/
