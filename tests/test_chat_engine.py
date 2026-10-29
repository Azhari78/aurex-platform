"""Unit tests for AIA Chat Assistant Engine and /api/chat endpoint."""

from fastapi.testclient import TestClient
from aurex.dashboard.app import app
from aurex.dashboard.chat_engine import generate_chat_response


def test_chat_engine_greetings():
    telemetry = {
        "usd_total": "10,000.00",
        "usd_available": "10,000.00",
        "myr_total": "47,200.00",
        "open_positions": [],
        "realized_pnl": 0.0,
        "win_rate": 0.0,
        "kill_switch": False
    }
    reply = generate_chat_response("Salam, siapa kamu?", telemetry)
    assert "AIA" in reply
    assert "Aurex" in reply


def test_chat_engine_balance_query():
    telemetry = {
        "usd_total": "15,250.00",
        "usd_available": "12,000.00",
        "myr_total": "71,980.00",
        "open_positions": [],
        "realized_pnl": 125.50,
        "win_rate": 75.0,
        "kill_switch": False
    }
    reply = generate_chat_response("Berapa baki duit kita sekarang?", telemetry)
    assert "$15,250.00 USD" in reply
    assert "RM 71,980.00" in reply
    assert "125.50" in reply


def test_chat_engine_safety_query():
    telemetry = {
        "usd_total": "10,000.00",
        "usd_available": "10,000.00",
        "myr_total": "47,200.00",
        "open_positions": [],
        "realized_pnl": 0.0,
        "win_rate": 0.0,
        "kill_switch": False
    }
    reply = generate_chat_response("Adakah selamat duit saya? Takut lebur", telemetry)
    assert "Risk Governor" in reply
    assert "Stop Loss" in reply


def test_chat_api_endpoint():
    client = TestClient(app)
    response = client.post("/api/chat", json={"message": "Macam mana bot ni buat untung?"})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "timestamp" in data
    assert len(data["reply"]) > 20


def test_chat_key_detection():
    telemetry = {
        "usd_total": "10,000.00",
        "usd_available": "10,000.00",
        "myr_total": "47,200.00",
        "open_positions": [],
        "realized_pnl": 0.0,
        "win_rate": 0.0,
        "kill_switch": False
    }
    # Test detecting AQ. key
    reply_aq = generate_chat_response("YOUR_GEMINI_API_KEY_HERE", telemetry)
    assert "Google Gemini API Key" in reply_aq
    assert "berjaya dikesan" in reply_aq

    # Test detecting AIzaSy key
    reply_aiza = generate_chat_response("AIzaSyAbc123def456ghi789jkl012mno345pqr", telemetry)
    assert "Google Gemini API Key" in reply_aiza
    assert "berjaya dikesan" in reply_aiza


def test_save_key_endpoint():
    client = TestClient(app)
    res = client.post("/api/save-ai-key", json={"api_key": "YOUR_GEMINI_API_KEY_HERE"})
    assert res.status_code == 200
    assert res.json()["status"] == "SAVED"
