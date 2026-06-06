from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility.
    tomllib = None


@dataclass(frozen=True)
class RuleResult:
    label: str
    matched: bool
    reasons: list[str]


def load_rules(path: str | Path) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    payload = tomllib.loads(text) if tomllib is not None else parse_rule_toml(text)
    rules = payload.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("Rule file must define [[rules]] entries.")
    for index, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict) or not rule.get("label"):
            raise ValueError(f"Rule {index} must define a label.")
    return rules


def parse_rule_toml(text: str) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line == "[[rules]]":
            current = {}
            rules.append(current)
            continue
        if current is None or "=" not in line:
            raise ValueError("Fallback TOML parser only supports [[rules]] entries with key = value pairs.")
        key, value = [part.strip() for part in line.split("=", 1)]
        current[key] = parse_toml_value(value)
    return {"rules": rules}


def parse_toml_value(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_toml_value(part.strip()) for part in inner.split(",")]
    raise ValueError(f"Unsupported TOML value: {value}")


def load_issue(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "issue" in payload and isinstance(payload["issue"], dict):
        payload = payload["issue"]
    return {
        "title": str(payload.get("title", "")),
        "body": str(payload.get("body", "")),
        "author": str(payload.get("author") or payload.get("user", {}).get("login", "")),
        "labels": normalize_labels(payload.get("labels", [])),
    }


def normalize_labels(labels: Any) -> list[str]:
    normalized: list[str] = []
    if not isinstance(labels, list):
        return normalized
    for label in labels:
        if isinstance(label, str):
            normalized.append(label)
        elif isinstance(label, dict) and isinstance(label.get("name"), str):
            normalized.append(label["name"])
    return normalized


def contains_any(text: str, needles: Any) -> tuple[bool, list[str]]:
    if not isinstance(needles, list):
        return False, []
    lowered = text.lower()
    matched = [str(needle) for needle in needles if str(needle).lower() in lowered]
    return bool(matched), matched


def regex_any(text: str, patterns: Any) -> tuple[bool, list[str]]:
    if not isinstance(patterns, list):
        return False, []
    matched: list[str] = []
    for pattern in patterns:
        pattern_text = str(pattern)
        try:
            if re.search(pattern_text, text, re.IGNORECASE):
                matched.append(pattern_text)
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern {pattern_text!r}: {exc}") from exc
    return bool(matched), matched


def author_matches(author: str, expected: Any) -> tuple[bool, list[str]]:
    if not isinstance(expected, list):
        return False, []
    lowered = author.lower()
    matched = [str(item) for item in expected if str(item).lower() == lowered]
    return bool(matched), matched


def label_condition(labels: list[str], expected: Any, present: bool) -> tuple[bool, list[str]]:
    if not isinstance(expected, list):
        return False, []
    lowered_labels = {label.lower() for label in labels}
    matched = [str(item) for item in expected if (str(item).lower() in lowered_labels) is present]
    return bool(matched), matched


def evaluate_rule(rule: dict[str, Any], issue: dict[str, Any]) -> RuleResult:
    checks: list[tuple[bool, str]] = []

    matched, words = contains_any(issue["title"], rule.get("title_contains"))
    if words:
        checks.append((matched, "title contains " + ", ".join(words)))
    elif "title_contains" in rule:
        checks.append((False, "title did not match"))

    matched, patterns = regex_any(issue["title"], rule.get("title_matches"))
    if patterns:
        checks.append((matched, "title matches " + ", ".join(patterns)))
    elif "title_matches" in rule:
        checks.append((False, "title regex did not match"))

    matched, words = contains_any(issue["body"], rule.get("body_contains"))
    if words:
        checks.append((matched, "body contains " + ", ".join(words)))
    elif "body_contains" in rule:
        checks.append((False, "body did not match"))

    matched, patterns = regex_any(issue["body"], rule.get("body_matches"))
    if patterns:
        checks.append((matched, "body matches " + ", ".join(patterns)))
    elif "body_matches" in rule:
        checks.append((False, "body regex did not match"))

    matched, authors = author_matches(issue["author"], rule.get("author_is"))
    if authors:
        checks.append((matched, "author is " + ", ".join(authors)))
    elif "author_is" in rule:
        checks.append((False, "author did not match"))

    matched, labels = label_condition(issue["labels"], rule.get("label_present"), True)
    if labels:
        checks.append((matched, "label present " + ", ".join(labels)))
    elif "label_present" in rule:
        checks.append((False, "required label missing"))

    matched, labels = label_condition(issue["labels"], rule.get("label_missing"), False)
    if labels:
        checks.append((matched, "label missing " + ", ".join(labels)))
    elif "label_missing" in rule:
        checks.append((False, "forbidden label present"))

    if not checks:
        return RuleResult(label=str(rule["label"]), matched=False, reasons=["rule has no conditions"])

    mode = str(rule.get("match", "any")).lower()
    matched_rule = all(value for value, _ in checks) if mode == "all" else any(value for value, _ in checks)
    reasons = [reason for value, reason in checks if value] or [reason for _, reason in checks]
    return RuleResult(label=str(rule["label"]), matched=matched_rule, reasons=reasons)


def apply_rules(rules: list[dict[str, Any]], issue: dict[str, Any]) -> list[RuleResult]:
    return [evaluate_rule(rule, issue) for rule in rules]


def selected_labels(results: list[RuleResult]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for result in results:
        key = result.label.lower()
        if result.matched and key not in seen:
            labels.append(result.label)
            seen.add(key)
    return labels


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply deterministic TOML issue triage rules.")
    parser.add_argument("--rules", required=True, help="Path to TOML rules.")
    parser.add_argument("--issue", required=True, help="Path to a GitHub issue JSON payload.")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format.")
    parser.add_argument("--explain", action="store_true", help="Include matching explanations in JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    issue = load_issue(args.issue)
    results = apply_rules(load_rules(args.rules), issue)
    labels = selected_labels(results)

    if args.format == "text":
        print("\n".join(labels))
        return 0

    payload: dict[str, Any] = {"labels": labels}
    if args.explain:
        payload["results"] = [asdict(result) for result in results]
    print(json.dumps(payload, indent=2))
    return 0
