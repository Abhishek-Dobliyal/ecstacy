from __future__ import annotations

import pandas as pd

from ecstacy.config import defaults
from ecstacy.widgets.table import filter_frame, sort_frame


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["us", "eu", "us", "eu"],
            "value": [10.0, 15.0, 12.0, 8.0],
            "count": [3, 5, 4, 2],
        }
    )


def test_filter_frame_no_search_returns_all():
    result = filter_frame(_sample(), "")
    assert len(result) == 4


def test_filter_frame_substring_match():
    result = filter_frame(_sample(), "eu")
    assert len(result) == 2
    assert set(result["region"]) == {"eu"}


def test_filter_frame_case_insensitive():
    result = filter_frame(_sample(), "US")
    assert len(result) == 2


def test_filter_frame_no_match():
    result = filter_frame(_sample(), "xyz")
    assert len(result) == 0


def test_sort_frame_ascending():
    result = sort_frame(_sample(), "value", ascending=True)
    assert list(result["value"]) == [8.0, 10.0, 12.0, 15.0]


def test_sort_frame_descending():
    result = sort_frame(_sample(), "value", ascending=False)
    assert list(result["value"]) == [15.0, 12.0, 10.0, 8.0]


def test_sort_frame_missing_column_returns_unchanged():
    frame = _sample()
    result = sort_frame(frame, "missing", ascending=True)
    assert len(result) == 4


def test_filter_then_sort():
    filtered = filter_frame(_sample(), "us")
    result = sort_frame(filtered, "value", ascending=False)
    assert list(result["value"]) == [12.0, 10.0]
