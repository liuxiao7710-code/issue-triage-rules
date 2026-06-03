from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from issue_triage_rules.cli import apply_rules, evaluate_rule, load_issue, selected_labels


class IssueTriageRulesTests(unittest.TestCase):
    def test_rule_matches_title(self) -> None:
        issue = {"title": "Crash on startup", "body": "", "author": "alice", "labels": []}
        rule = {"label": "bug", "title_contains": ["crash"]}

        result = evaluate_rule(rule, issue)

        self.assertTrue(result.matched)
        self.assertEqual(result.label, "bug")

    def test_all_mode_requires_every_condition(self) -> None:
        issue = {"title": "Question", "body": "steps included", "author": "alice", "labels": []}
        rule = {"label": "needs-info", "title_contains": ["bug"], "body_contains": ["steps"], "match": "all"}

        self.assertFalse(evaluate_rule(rule, issue).matched)

    def test_selected_labels_are_unique(self) -> None:
        issue = {"title": "Crash", "body": "traceback", "author": "alice", "labels": []}
        rules = [
            {"label": "bug", "title_contains": ["crash"]},
            {"label": "bug", "body_contains": ["traceback"]},
        ]

        labels = selected_labels(apply_rules(rules, issue))

        self.assertEqual(labels, ["bug"])

    def test_load_issue_accepts_github_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_path = Path(temp_dir) / "issue.json"
            issue_path.write_text(
                json.dumps({"issue": {"title": "Hi", "body": "Body", "user": {"login": "alice"}, "labels": [{"name": "bug"}]}}),
                encoding="utf-8",
            )

            issue = load_issue(issue_path)

            self.assertEqual(issue["author"], "alice")
            self.assertEqual(issue["labels"], ["bug"])

    def test_cli_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            rules = Path(temp_dir) / "rules.toml"
            issue = Path(temp_dir) / "issue.json"
            rules.write_text('[[rules]]\nlabel = "bug"\ntitle_contains = ["crash"]\n', encoding="utf-8")
            issue.write_text(json.dumps({"title": "Crash now", "body": "", "author": "alice"}), encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, "-m", "issue_triage_rules", "--rules", str(rules), "--issue", str(issue)],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
                text=True,
                capture_output=True,
                check=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(payload["labels"], ["bug"])


if __name__ == "__main__":
    unittest.main()
