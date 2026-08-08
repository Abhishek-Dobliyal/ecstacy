from __future__ import annotations

import numpy as np
import pandas as pd

from ecstacy.core.dataset import DataSet


def test_schema_infers_roles(sample_frame):
    dataset = DataSet.from_dataframe(sample_frame, source_id="s", kind="test")
    schema = dataset.schema
    assert schema.time_columns == ["date"]
    assert set(schema.value_columns) == {"value", "count"}
    assert schema.category_columns == ["region"]
    assert dataset.meta.rows == 2


def test_diet_downcasts_small_integers():
    frame = pd.DataFrame({"a": np.array([1, 2, 3], dtype="int64")})
    dataset = DataSet.from_dataframe(frame, source_id="s", kind="test")
    assert dataset.frame["a"].dtype == np.int8


def test_diet_downcasts_floats_to_float32():
    frame = pd.DataFrame({"a": np.array([1.5, 2.5], dtype="float64")})
    dataset = DataSet.from_dataframe(frame, source_id="s", kind="test")
    assert dataset.frame["a"].dtype == np.float32


def test_diet_converts_low_cardinality_strings_to_category():
    frame = pd.DataFrame({"region": ["us", "eu", "us", "eu", "us"]})
    dataset = DataSet.from_dataframe(frame, source_id="s", kind="test")
    assert isinstance(dataset.frame["region"].dtype, pd.CategoricalDtype)


def test_diet_keeps_high_cardinality_strings_as_object():
    frame = pd.DataFrame({"id": [f"id-{i}" for i in range(100)]})
    dataset = DataSet.from_dataframe(frame, source_id="s", kind="test")
    assert not isinstance(dataset.frame["id"].dtype, pd.CategoricalDtype)


def test_diet_preserves_datetime_columns():
    frame = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-01-02"])})
    dataset = DataSet.from_dataframe(frame, source_id="s", kind="test")
    assert pd.api.types.is_datetime64_any_dtype(dataset.frame["date"])


def test_diet_handles_empty_frame():
    frame = pd.DataFrame({"a": pd.Series([], dtype="int64")})
    dataset = DataSet.from_dataframe(frame, source_id="s", kind="test")
    assert dataset.meta.rows == 0


def test_diet_disabled_preserves_original_dtypes():
    frame = pd.DataFrame({"a": np.array([1, 2, 3], dtype="int64")})
    dataset = DataSet.from_dataframe(frame, source_id="s", kind="test", diet=False)
    assert dataset.frame["a"].dtype == np.int64


def test_diet_does_not_mutate_caller_frame():
    """Downcasting must not alter the frame the caller still holds sources
    may cache and re-fetch the same frame object across refresh cycles."""
    frame = pd.DataFrame({"a": np.array([1, 2, 3], dtype="int64")})
    DataSet.from_dataframe(frame, source_id="s", kind="test")
    assert frame["a"].dtype == np.int64


def test_diet_preserves_role_classification():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"] * 5),
            "region": ["us", "eu"] * 5,
            "value": list(range(10)),
        }
    )
    dataset = DataSet.from_dataframe(frame, source_id="s", kind="test")
    assert dataset.schema.time_columns == ["date"]
    assert dataset.schema.value_columns == ["value"]
    assert dataset.schema.category_columns == ["region"]
