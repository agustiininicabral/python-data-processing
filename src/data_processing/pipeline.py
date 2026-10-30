"""CLI and transformation functions for the sample sales dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("order_id", "order_date", "product", "quantity", "unit_price")
NUMERIC_COLUMNS = ("quantity", "unit_price")


class DataValidationError(ValueError):
    """Raised when an input dataset cannot be processed safely."""


def load_data(input_path: str | Path) -> pd.DataFrame:
    """Load a CSV and verify that all required columns are present."""
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    try:
        frame = pd.read_csv(path)
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DataValidationError(f"Could not parse CSV: {exc}") from exc

    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {', '.join(missing)}")
    return frame.loc[:, list(REQUIRED_COLUMNS)].copy()


def clean_data(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (accepted, rejected); every rejected row includes a reason."""
    if not set(REQUIRED_COLUMNS).issubset(frame.columns):
        raise DataValidationError("Input frame does not contain the required schema")

    data = frame.loc[:, list(REQUIRED_COLUMNS)].copy()
    data["order_id"] = data["order_id"].astype("string").str.strip()
    data["product"] = data["product"].astype("string").str.strip()
    data["order_date"] = pd.to_datetime(data["order_date"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    reasons: list[list[str]] = [[] for _ in range(len(data))]
    checks = {
        "missing_order_id": data["order_id"].isna() | data["order_id"].eq(""),
        "invalid_order_date": data["order_date"].isna(),
        "missing_product": data["product"].isna() | data["product"].eq(""),
        "invalid_quantity": data["quantity"].isna() | (data["quantity"] <= 0),
        "invalid_unit_price": data["unit_price"].isna() | (data["unit_price"] < 0),
    }
    for reason, mask in checks.items():
        for position in np.flatnonzero(mask.to_numpy()):
            reasons[position].append(reason)

    seen: set[str] = set()
    for position, order_id in enumerate(data["order_id"].tolist()):
        if not reasons[position] and order_id in seen:
            reasons[position].append("duplicate_order_id")
        elif not reasons[position]:
            seen.add(str(order_id))

    rejected_mask = np.array([bool(items) for items in reasons])
    rejected = data.loc[rejected_mask].copy()
    rejected["rejection_reason"] = [
        ";".join(items) for items, is_rejected in zip(reasons, rejected_mask) if is_rejected
    ]

    accepted = data.loc[~rejected_mask].copy()
    accepted["order_id"] = accepted["order_id"].astype(str)
    accepted["product"] = accepted["product"].astype(str)
    accepted["quantity"] = accepted["quantity"].astype("int64")
    accepted["unit_price"] = accepted["unit_price"].astype(float)
    accepted["revenue"] = (accepted["quantity"] * accepted["unit_price"]).round(2)
    accepted = accepted.sort_values(["order_date", "order_id"]).reset_index(drop=True)
    return accepted, rejected.reset_index(drop=True)


def build_summary(cleaned: pd.DataFrame, rejected: pd.DataFrame, source_rows: int) -> dict[str, Any]:
    """Build stable, JSON-serializable data quality and business metrics."""
    total_revenue = round(float(cleaned["revenue"].sum()), 2) if not cleaned.empty else 0.0
    return {
        "source_rows": int(source_rows),
        "accepted_rows": int(len(cleaned)),
        "rejected_rows": int(len(rejected)),
        "acceptance_rate": round(len(cleaned) / source_rows, 4) if source_rows else 0.0,
        "total_revenue": total_revenue,
        "average_order_value": round(total_revenue / len(cleaned), 2) if len(cleaned) else 0.0,
        "unique_products": int(cleaned["product"].nunique()) if len(cleaned) else 0,
        "rejection_reasons": (
            rejected["rejection_reason"].str.split(";").explode().value_counts().sort_index().to_dict()
            if len(rejected) else {}
        ),
    }


def monthly_revenue(cleaned: pd.DataFrame) -> pd.DataFrame:
    """Aggregate accepted revenue by calendar month."""
    if cleaned.empty:
        return pd.DataFrame(columns=["month", "revenue", "orders"])
    result = cleaned.assign(month=cleaned["order_date"].dt.to_period("M").astype(str))
    return (
        result.groupby("month", as_index=False)
        .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
        .assign(revenue=lambda x: x["revenue"].round(2))
        .sort_values("month")
        .reset_index(drop=True)
    )


def run_pipeline(input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Execute the full pipeline and persist all outputs."""
    raw = load_data(input_path)
    cleaned, rejected = clean_data(raw)
    summary = build_summary(cleaned, rejected, len(raw))
    monthly = monthly_revenue(cleaned)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(destination / "cleaned_sales.csv", index=False, date_format="%Y-%m-%d")
    rejected.to_csv(destination / "rejected_sales.csv", index=False, date_format="%Y-%m-%d")
    monthly.to_csv(destination / "monthly_revenue.csv", index=False)
    (destination / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean sales data and generate quality/KPI outputs.")
    parser.add_argument("--input", required=True, help="Path to source CSV")
    parser.add_argument("--output", required=True, help="Directory for generated outputs")
    args = parser.parse_args()
    summary = run_pipeline(args.input, args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
