# Contributing

Thanks for helping improve `issue-triage-rules`.

## Local setup

```bash
python -m pip install -e .
python -m unittest discover -s tests
```

## Good first contributions

- Add new deterministic rule conditions.
- Improve GitHub Actions examples.
- Add fixtures for real issue payloads.
- Improve explanation output.

## Pull request checklist

- Keep matching behavior deterministic.
- Add tests for each new rule condition.
- Preserve Python 3.10 compatibility.
- Update README examples when rule syntax changes.
