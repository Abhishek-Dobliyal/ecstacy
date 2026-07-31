from __future__ import annotations

import pytest

from ecstacy.core.transforms import Transform, TransformError, parse_transform_query


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


def test_parse_transform_query_where():
    t = parse_transform_query("where value > 12")
    assert t.where == "value > 12"
    assert t.group_by is None


def test_parse_transform_query_group_by_agg():
    t = parse_transform_query("group_by region | agg mean")
    assert t.group_by == ["region"]
    assert t.agg == "mean"


def test_parse_transform_query_full():
    t = parse_transform_query(
        "where value > 100 | group_by region, date | agg mean | select region, value | limit 10"
    )
    assert t.where == "value > 100"
    assert t.group_by == ["region", "date"]
    assert t.agg == "mean"
    assert t.select == ["region", "value"]
    assert t.limit == 10


def test_parse_transform_query_empty():
    t = parse_transform_query("")
    assert t.where is None
    assert t.group_by is None
    assert t.agg == "sum"


def test_parse_transform_query_newline_separator():
    t = parse_transform_query("where value > 10\ngroup_by region\nagg count")
    assert t.where == "value > 10"
    assert t.group_by == ["region"]
    assert t.agg == "count"


def test_parse_transform_query_invalid_limit():
    with pytest.raises(TransformError):
        parse_transform_query("limit abc")


def test_parse_transform_query_sql_input_gets_dsl_hint():
    with pytest.raises(TransformError, match="not SQL"):
        parse_transform_query("select * from metrics")
    with pytest.raises(TransformError, match="not SQL"):
        parse_transform_query("SELECT region, value FROM metrics WHERE value > 10")


def test_parse_transform_query_dsl_select_clause_not_flagged_as_sql():
    """The DSL's own select clause (no FROM) must keep working."""
    t = parse_transform_query("select region, value")
    assert t.select == ["region", "value"]


def test_where_single_equals_hint():
    """`where region = US` — the classic single-= mistake — gets a clear hint
    instead of pandas' cryptic 'cannot assign without a target object'."""
    with pytest.raises(TransformError, match="use == to compare"):
        Transform(where="region = US").apply(
            __import__("pandas").DataFrame({"region": ["us"], "value": [1]})
        )


def test_where_unquoted_string_hint():
    """`where region == US` — unquoted string — suggests quoting the value."""
    import pandas as pd

    with pytest.raises(TransformError, match="quote string values.*'US'"):
        Transform(where="region == US").apply(
            pd.DataFrame({"region": ["us"], "value": [1]})
        )


def test_where_quoted_equals_inside_string_not_flagged():
    """A string value containing '=' must not trigger the lone-= check."""
    import pandas as pd

    result = Transform(where="region == 'u=s'").apply(
        pd.DataFrame({"region": ["us", "u=s"], "value": [1, 2]})
    )
    assert len(result) == 1
    assert result.iloc[0]["region"] == "u=s"


def test_where_valid_string_comparison_works():
    import pandas as pd

    result = Transform(where="region == 'us'").apply(
        pd.DataFrame({"region": ["us", "eu"], "value": [1, 2]})
    )
    assert len(result) == 1


def test_parse_transform_query_applies_to_frame(sample_frame):
    t = parse_transform_query("where value > 12 | group_by region | agg sum")
    result = t.apply(sample_frame)
    assert len(result) == 1
    assert result.iloc[0]["region"] == "eu"
