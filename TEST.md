# Login (stores base URL + token; validates via /myself)
jira auth login
# Base URL: https://jira.yourdomain.com
# Token: <paste PAT/Bearer>

# Verify who you are
jira auth whoami

# (Optional) Try overrides
jira auth whoami --base-url https://jira.yourdomain.com --token "$JIRA_BEARER_TOKEN"

# (Optional) Logout
jira auth logout


jira ticket create \
  -p PP \
  -t Task \
  -s "CLI test: create ticket" \
  --desc "Created by jira test" \
  --label jira --label e2e \
  --priority Normal

jira ticket comment PP-1234 -b "✅ Comment from jira test."
# or open your editor:
jira ticket comment PP-1234

# Project open issues
jira ticket list -p PP

# Only yours
jira ticket list -p PP --mine

# Someones tickets:

jira ticket list -p PP --assignee ''

# Include Done/Closed
jira ticket list -p PP --all

# With extra JQL
jira ticket list -p PP --jql 'labels = jira'


# Create (raw JSON)
jira ticket create -p PP -t Task -s "JSON mode" --json

# List (raw JSON)
jira ticket list -p PP -n 5 --json
