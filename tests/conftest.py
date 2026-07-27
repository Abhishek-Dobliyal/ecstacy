from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def sample_csv() -> Path:
    return DATA_DIR / "sample.csv"


@pytest.fixture
def sample_json() -> Path:
    return DATA_DIR / "sample.json"


@pytest.fixture
def sample_ndjson() -> Path:
    return DATA_DIR / "sample.ndjson"


@pytest.fixture
def sample_parquet() -> Path:
    return DATA_DIR / "sample.parquet"


@pytest.fixture
def empty_csv() -> Path:
    return DATA_DIR / "empty.csv"


@pytest.fixture
def duplicate_csv() -> Path:
    return DATA_DIR / "duplicate.csv"


@pytest.fixture
def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "region": ["us", "eu"],
            "value": [10.0, 15.0],
            "count": [3, 5],
        }
    )
