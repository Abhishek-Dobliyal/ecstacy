from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.core.transforms import Transform, TransformError


def test_aggregate_groups_and_sums(sample_frame):
    result = Transform(group_by=["region"], agg="sum").apply(sample_frame)
    assert set(result["region"]) == {"us", "eu"}
    assert len(result) == 2


def test_where_filters_rows(sample_frame):
    result = Transform(where="value > 12").apply(sample_frame)
    assert len(result) == 1
    assert result.iloc[0]["region"] == "eu"


def test_transform_invalid_where(sample_frame):
    with pytest.raises(TransformError):
        Transform(where="invalid_column > 12").apply(sample_frame)


def test_transform_missing_group_by(sample_frame):
    with pytest.raises(TransformError):
        Transform(group_by=["missing"]).apply(sample_frame)


def test_transform_negative_limit(sample_frame):
    with pytest.raises(TransformError):
        Transform(limit=-1).apply(sample_frame)


def test_transform_select_columns(sample_frame):
    result = Transform(select=["region", "value"]).apply(sample_frame)
    assert list(result.columns) == ["region", "value"]


def test_transform_resample_time(sample_frame):
    result = Transform(resample="D", time_column="date", agg="sum").apply(sample_frame)
    assert len(result) > 0
    assert "date" in result.columns
