# issue-triage-rules

[![CI](https://github.com/liuxiao7710-code/issue-triage-rules/actions/workflows/ci.yml/badge.svg)](https://github.com/liuxiao7710-code/issue-triage-rules/actions/workflows/ci.yml)

`issue-triage-rules` labels issue payloads using plain TOML rules. It is intentionally deterministic: no network calls, no model dependency, and no surprise labels.

Use it when a project wants lightweight first-pass triage for issues from GitHub Actions, bots, or local scripts.

## Install

```bash
python -m pip install .
```

## Rule file

```toml
[[rules]]
label = "bug"
title_contains = ["crash", "error", "exception"]
body_contains = ["traceback", "stack trace"]
match = "any"

[[rules]]
label = "dependencies"
author_is = ["dependabot[bot]", "renovate[bot]"]

[[rules]]
label = "needs-info"
body_contains = ["to reproduce", "steps"]
match = "all"

[[rules]]
label = "regression"
title_matches = ["v[0-9]+\\.[0-9]+\\.[0-9]+"]
```

## Issue payload

```json
{
  "title": "Crash when config is empty",
  "body": "The stack trace points to config parsing.",
  "author": "alice",
  "labels": []
}
```

## Usage

```bash
issue-triage-rules --rules examples/rules.toml --issue examples/issue.json
issue-triage-rules --rules examples/rules.toml --issue examples/issue.json --explain
issue-triage-rules --rules examples/rules.toml --issue examples/issue.json --format text
```

Example JSON output:

```json
{
  "labels": [
    "bug"
  ],
  "results": [
    {
      "label": "bug",
      "matched": true,
      "reasons": [
        "title contains crash",
        "body contains stack trace"
      ]
    }
  ]
}
```

## GitHub Actions sketch

```yaml
name: Issue triage
on:
  issues:
    types: [opened, edited]
jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install .
      - run: issue-triage-rules --rules .github/triage-rules.toml --issue "$GITHUB_EVENT_PATH"
```

## Maintenance roadmap

- Add conditions for issue author association and changed labels.
- Add a dry-run GitHub Actions workflow example.
- Add fixture payloads for opened, edited, and reopened issue events.
- Document recommended rule organization for larger projects.

## Development

```bash
python -m unittest discover -s tests
```

## License

MIT
