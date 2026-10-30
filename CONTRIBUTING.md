# Contributing

## Development setup

Use Python 3.11 or newer and create an isolated virtual environment.

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest --cov=data_processing --cov-report=term-missing
```

## Change guidelines

- Keep transformations deterministic and avoid modifying source data.
- Add tests for new validation rules and edge cases.
- Preserve actionable rejection reasons for invalid records.
- Update the README when command-line behavior or generated outputs change.

All pull requests run the GitHub Actions test matrix on Python 3.11, 3.12 and 3.13.
