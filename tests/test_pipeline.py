import json
import runpy
import sys

import pandas as pd
import pytest

from data_processing.pipeline import (
    DataValidationError,
    build_summary,
    clean_data,
    load_data,
    monthly_revenue,
    run_pipeline,
)


@pytest.fixture
def sample_frame():
    return pd.DataFrame(
        [
            ["A-001", "2025-01-03", "Keyboard", 2, 50.0],
            ["A-002", "2025-01-15", "Mouse", 1, 25.0],
            ["A-003", "2025-02-01", "Monitor", 1, 200.0],
            ["A-003", "2025-02-02", "Monitor", 1, 200.0],
            ["A-004", "not-a-date", "Cable", 3, 5.0],
            ["A-005", "2025-02-03", "Bad quantity", 0, 10.0],
            ["A-006", "2025-02-04", "Bad price", 1, -1.0],
            ["A-007", "2025-02-05", "", 1, 10.0],
        ],
        columns=["order_id", "order_date", "product", "quantity", "unit_price"],
    )


def test_clean_data_accepts_valid_rows_and_explains_rejections(sample_frame):
    accepted, rejected = clean_data(sample_frame)
    assert accepted["order_id"].tolist() == ["A-001", "A-002", "A-003"]
    assert len(rejected) == 5
    assert "duplicate_order_id" in rejected["rejection_reason"].tolist()
    assert "invalid_order_date" in rejected["rejection_reason"].tolist()
    assert accepted["revenue"].tolist() == [100.0, 25.0, 200.0]


def test_clean_data_does_not_mutate_input(sample_frame):
    original = sample_frame.copy(deep=True)
    clean_data(sample_frame)
    pd.testing.assert_frame_equal(sample_frame, original)


def test_clean_data_rejects_missing_schema():
    with pytest.raises(DataValidationError, match="required schema"):
        clean_data(pd.DataFrame({"order_id": ["A-001"]}))


def test_summary_metrics(sample_frame):
    accepted, rejected = clean_data(sample_frame)
    summary = build_summary(accepted, rejected, len(sample_frame))
    assert summary["source_rows"] == 8
    assert summary["accepted_rows"] == 3
    assert summary["rejected_rows"] == 5
    assert summary["total_revenue"] == 325.0
    assert summary["average_order_value"] == pytest.approx(108.33, abs=0.01)
    assert summary["rejection_reasons"]["duplicate_order_id"] == 1


def test_monthly_revenue(sample_frame):
    accepted, _ = clean_data(sample_frame)
    result = monthly_revenue(accepted)
    assert result.to_dict("records") == [
        {"month": "2025-01", "revenue": 125.0, "orders": 2},
        {"month": "2025-02", "revenue": 200.0, "orders": 1},
    ]


def test_load_data_rejects_missing_columns(tmp_path):
    source = tmp_path / "bad.csv"
    pd.DataFrame({"order_id": ["A"]}).to_csv(source, index=False)
    with pytest.raises(DataValidationError, match="Missing required columns"):
        load_data(source)


def test_load_data_rejects_malformed_csv(tmp_path):
    source = tmp_path / "malformed.csv"
    source.write_text('order_id,order_date,product,quantity,unit_price\n"A-001,2025-01-01,Mouse,1,10\n')
    with pytest.raises(DataValidationError, match="Could not parse CSV"):
        load_data(source)


def test_load_data_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_data(tmp_path / "missing.csv")


def test_pipeline_writes_all_outputs(tmp_path, sample_frame):
    source = tmp_path / "sales.csv"
    output = tmp_path / "out"
    sample_frame.to_csv(source, index=False)
    summary = run_pipeline(source, output)
    assert summary["accepted_rows"] == 3
    assert {p.name for p in output.iterdir()} == {
        "cleaned_sales.csv", "rejected_sales.csv", "monthly_revenue.csv", "summary.json"
    }
    assert json.loads((output / "summary.json").read_text())["total_revenue"] == 325.0


def test_empty_dataset_has_zero_metrics():
    empty = pd.DataFrame(columns=["order_id", "order_date", "product", "quantity", "unit_price"])
    accepted, rejected = clean_data(empty)
    summary = build_summary(accepted, rejected, 0)
    assert accepted.empty
    assert rejected.empty
    assert summary["acceptance_rate"] == 0.0
    assert summary["total_revenue"] == 0.0
    assert monthly_revenue(accepted).empty


def test_module_entrypoint_runs_cli(tmp_path, sample_frame, monkeypatch, capsys):
    source = tmp_path / "sales.csv"
    output = tmp_path / "cli-output"
    sample_frame.to_csv(source, index=False)
    monkeypatch.setattr(sys, "argv", ["data_processing", "--input", str(source), "--output", str(output)])
    runpy.run_module("data_processing", run_name="__main__")
    assert '"accepted_rows": 3' in capsys.readouterr().out
    assert (output / "summary.json").is_file()
