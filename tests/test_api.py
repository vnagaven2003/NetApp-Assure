"""API contract checks; network connectivity is tested separately later."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_contract(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_inventory_and_detail_agree(client):
    response = client.get("/devices")
    assert response.status_code == 200
    devices = response.json()
    assert {device["name"] for device in devices} == {"r1", "r2"}
    assert len({device["id"] for device in devices}) == len(devices)
    for device in devices:
        detail = client.get(f"/devices/{device['id']}")
        assert detail.status_code == 200
        assert detail.json() == device


def test_unknown_device(client):
    response = client.get("/devices/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found"}


@pytest.mark.parametrize("device_id", ["abc", "0", "-1", "1.5"])
def test_invalid_device_id(client, device_id):
    response = client.get(f"/devices/{device_id}")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "device_id"]


def test_inventory_is_read_only(client):
    response = client.post("/devices", json={"name": "unexpected"})
    assert response.status_code == 405
