"""Unit tests for MT5 Broker Adapter and endpoints."""

from fastapi.testclient import TestClient
from aurex.dashboard.app import app
from aurex.adapters.mt5_adapter import MT5Adapter


def test_mt5_adapter_initialization():
    adapter = MT5Adapter()
    summary = adapter.get_summary()
    assert "login" in summary
    assert "server" in summary
    assert summary["login"] == 5057835635
    assert summary["server"] == "MetaQuotes-Demo"


def test_mt5_status_endpoint():
    client = TestClient(app)
    res = client.get("/api/mt5/status")
    assert res.status_code == 200
    data = res.json()
    assert "login" in data
    assert "server" in data
    assert data["login"] == 5057835635


def test_chat_with_mt5_query():
    client = TestClient(app)
    res = client.post("/api/chat", json={"message": "Macam mana status akaun mt5 demo kita?"})
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert "MT5" in data["reply"] or "MetaTrader" in data["reply"]
