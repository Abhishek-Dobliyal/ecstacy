from __future__ import annotations

import pytest
from httpx import Request, Response

from ecstacy.sources.base import SourceError, SourceSpec, create_source


def _request() -> Request:
    return Request("GET", "https://api.example.com/items")


def test_rest_source_reads_json_array(monkeypatch):
    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(
            200,
            request=_request(),
            json=[
                {"date": "2024-01-01", "region": "us", "value": 10.0, "count": 3},
                {"date": "2024-01-02", "region": "eu", "value": 15.0, "count": 5},
            ],
        )

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(kind="rest", id="api", params={"url": "https://api.example.com/items"})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 2


def test_rest_source_digs_json_path(monkeypatch):
    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(
            200,
            request=_request(),
            json={
                "data": {
                    "items": [
                        {"date": "2024-01-01", "region": "us", "value": 10.0},
                    ]
                }
            },
        )

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(
        kind="rest",
        id="api",
        params={"url": "https://api.example.com/items", "json_path": "data.items"},
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 1


def test_rest_source_digs_array_index(monkeypatch):
    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(
            200, request=_request(),
            json={"data": {"items": [{"value": 1}, {"value": 2}]}},
        )

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(
        kind="rest",
        id="api",
        params={"url": "https://api.example.com/items", "json_path": "data.items.0"},
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 1


def test_rest_source_json_path_resolves_to_none(monkeypatch):
    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(200, request=_request(), json={"data": {"items": []}})

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(
        kind="rest",
        id="api",
        params={"url": "https://api.example.com/items", "json_path": "data.missing"},
    )
    with pytest.raises(SourceError):
        create_source(spec).fetch()


def test_rest_source_non_json_response(monkeypatch):
    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(200, request=_request(), text="not json")

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(kind="rest", id="api", params={"url": "https://api.example.com/items"})
    with pytest.raises(SourceError):
        create_source(spec).fetch()


def test_rest_source_http_error(monkeypatch):
    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(500, request=_request(), text="server error")

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(kind="rest", id="api", params={"url": "https://api.example.com/items"})
    with pytest.raises(SourceError):
        create_source(spec).fetch()


def test_rest_source_limits_rows(monkeypatch):
    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(
            200,
            request=_request(),
            json=[{"value": i} for i in range(10)],
        )

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(
        kind="rest", id="api", params={"url": "https://api.example.com/items", "max_rows": 3}
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 3


def test_rest_source_reuses_client_across_fetches(monkeypatch):
    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(200, request=_request(), json=[{"value": 1}])

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(kind="rest", id="api", params={"url": "https://api.example.com/items"})
    source = create_source(spec)
    source.fetch()
    first_client = source._client
    assert first_client is not None
    source.fetch()
    assert source._client is first_client


def test_rest_source_close_releases_client(monkeypatch):
    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(200, request=_request(), json=[{"value": 1}])

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(kind="rest", id="api", params={"url": "https://api.example.com/items"})
    source = create_source(spec)
    source.fetch()
    assert source._client is not None
    source.close()
    assert source._client is None
    source.fetch()
    assert source._client is not None
