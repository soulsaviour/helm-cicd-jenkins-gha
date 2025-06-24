import pytest

from app import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    return create_app().test_client()


def test_health_endpoints(client):
    assert client.get("/healthz").json == {"status": "ok"}
    assert client.get("/readyz").json == {"status": "ready"}


def test_index_reports_version(client):
    assert client.get("/").json == {"service": "inventory-api", "version": "1.2.3"}


def test_list_and_get_items(client):
    items = client.get("/items").json
    assert {item["sku"] for item in items} == {"sku-1001", "sku-1002", "sku-1003"}
    assert client.get("/items/sku-1002").json["name"] == "27-inch monitor"


def test_unknown_item_is_404(client):
    assert client.get("/items/sku-9999").status_code == 404
