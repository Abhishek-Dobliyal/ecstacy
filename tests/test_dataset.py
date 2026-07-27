from __future__ import annotations

from ecstacy.core.dataset import DataSet


def test_schema_infers_roles(sample_frame):
    dataset = DataSet.from_dataframe(sample_frame, source_id="s", kind="test")
    schema = dataset.schema
    assert schema.time_columns == ["date"]
    assert set(schema.value_columns) == {"value", "count"}
    assert schema.category_columns == ["region"]
    assert dataset.meta.rows == 2
