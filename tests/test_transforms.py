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


def test_parse_transform_query_empty_clauses_skipped():
    t = parse_transform_query("where x > 1 || group_by y")
    assert t.where == "x > 1"
    assert t.group_by == ["y"]


def test_parse_transform_query_only_pipe_separators():
    t = parse_transform_query("|where x > 1||group_by y|")
    assert t.where == "x > 1"
    assert t.group_by == ["y"]


def test_parse_transform_query_lone_equals_in_unquoted_value():
    import pandas as pd

    t = parse_transform_query("where x = 5")
    with pytest.raises(TransformError, match="use == to compare"):
        t.apply(pd.DataFrame({"x": [1, 2, 3]}))


def test_parse_transform_query_equals_in_quoted_string_ok():
    import pandas as pd

    t = parse_transform_query("where x == 'y=z'")
    assert t.where == "x == 'y=z'"
    result = t.apply(pd.DataFrame({"x": ["y=z", "other"], "val": [1, 2]}))
    assert len(result) == 1


def test_parse_transform_query_malformed_limit_fails():
    with pytest.raises(TransformError, match="invalid limit"):
        parse_transform_query("limit abc")


def test_parse_transform_query_sql_looking_input_fails():
    with pytest.raises(TransformError, match="not SQL"):
        parse_transform_query("select a, b from c")
    with pytest.raises(TransformError, match="not SQL"):
        parse_transform_query("SELECT * FROM x WHERE a > 1")


def test_parse_transform_query_unknown_keyword_ignored():
    t = parse_transform_query("where x > 1 | unknown_clause y | limit 5")
    assert t.where == "x > 1"
    assert t.limit == 5


def test_parse_transform_query_resample_and_time():
    t = parse_transform_query("resample D | time date | agg mean")
    assert t.resample == "D"
    assert t.time_column == "date"
    assert t.agg == "mean"


def test_parse_transform_query_select_with_spaces():
    t = parse_transform_query("select region ,  value  , count")
    assert t.select == ["region", "value", "count"]


def test_transform_limit_zero_returns_empty():
    import pandas as pd

    frame = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    result = Transform(limit=0).apply(frame)
    assert len(result) == 0
