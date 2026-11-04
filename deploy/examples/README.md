# Example: auto-run Airlock on every push (for consuming dev teams)

Copy `.github/workflows/airlock-review.yml` from this folder into the consuming repo,
set two repo secrets, and every push/PR gets a real Airlock review — verdict, receipts and
token spend — without installing anything.

```yaml
# .github/workflows/airlock-review.yml  (in the CONSUMING repo)
name: Airlock review
on:
  pull_request:
  push:
    branches: [main]

jobs:
  airlock:
    runs-on: ubuntu-latest
    steps:
      - name: Submit PR to Airlock
        run: |
          RESP=$(curl -s -X POST https://airlock.example.com/v1/runs \
            -H "X-API-Key: ${{ secrets.AIRLOCK_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{"pr_url": "${{ github.event.pull_request.html_url || format('https://github.com/{0}/pull/0', github.repository) }}"}')
          echo "run: $RESP"
      # Poll GET /v1/runs/{id} until completed; the verdict label + receipt link can be
      # posted back as a PR comment with gh api, or surfaced as a commit status.
```

Notes:
- The team's key is created once by an Airlock admin (scope `runs:write`), stored hashed,
  revocable from the admin page — a leaked team key never sees anyone else's runs
  (owner-filtered) and costs only that team's rate budget (5 runs/min default).
- Network anomalies (egress attempts, canary touches, denied writes) arrive in the same
  verdict — a push that phones home fails the review even with green tests.
