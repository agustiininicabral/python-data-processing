# Python Data Processing

![CI](https://github.com/agustiininicabral/python-data-processing/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A reproducible data-processing pipeline built with Python, pandas and NumPy. It cleans raw sales data, validates records, derives business metrics and exports auditable outputs.

## What it demonstrates

- Defensive CSV ingestion and schema validation
- Data cleaning with explicit rules and rejected-row reporting
- Type conversion, missing-value handling and duplicate detection
- Revenue and monthly KPI aggregation
- Reproducible command-line execution
- Unit tests and continuous integration

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m data_processing --input data/raw/sales.csv --output outputs
```

The command creates:
- `cleaned_sales.csv`: validated records
- `rejected_sales.csv`: rejected records with reasons
- `summary.json`: dataset quality and business KPIs
- `monthly_revenue.csv`: monthly revenue aggregation

## Data quality rules

A row is rejected when its order ID, order date, product, quantity or unit price is missing/invalid; quantity must be positive and unit price cannot be negative. Duplicate order IDs are rejected after the first valid occurrence. Currency values are calculated as quantity × unit price and rounded to two decimals.

## Project structure

```text
src/data_processing/
  __init__.py
  __main__.py
  pipeline.py
data/raw/sales.csv
tests/
  test_pipeline.py
outputs/                 # generated locally; ignored by Git
.github/workflows/ci.yml
```

## Run tests

```bash
python -m pytest
```

## Design notes

The pipeline is intentionally deterministic: it does not modify source files, uses explicit validation rules, and preserves rejection reasons for auditability. The sample dataset is synthetic and contains deliberately imperfect records for demonstration.

## License

MIT. See [LICENSE](LICENSE).
