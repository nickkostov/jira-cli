# Login (stores base URL + token; validates via /myself)
cashout auth login
# Base URL: https://jira.yourdomain.com
# Token: <paste PAT/Bearer>

# Verify who you are
cashout auth whoami

# (Optional) Try overrides
cashout auth whoami --base-url https://jira.yourdomain.com --token "$JIRA_BEARER_TOKEN"

# (Optional) Logout
cashout auth logout


cashout ticket create \
  -p PP \
  -t Task \
  -s "CLI test: create ticket" \
  --desc "Created by cashout test" \
  --label cashout --label e2e \
  --priority Normal

cashout ticket comment PP-1234 -b "✅ Comment from cashout test."
# or open your editor:
cashout ticket comment PP-1234

# Project open issues
cashout ticket list -p PP

# Only yours
cashout ticket list -p PP --mine

# Someones tickets:

cashout ticket list -p PP --assignee ''

# Include Done/Closed
cashout ticket list -p PP --all

# With extra JQL
cashout ticket list -p PP --jql 'labels = cashout'


# Create (raw JSON)
cashout ticket create -p PP -t Task -s "JSON mode" --json

# List (raw JSON)
cashout ticket list -p PP -n 5 --json
