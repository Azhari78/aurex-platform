"""Unit tests for Web3 and MetaMask Wallet Adapter, endpoints, and chat engine integration."""

from fastapi.testclient import TestClient
from aurex.dashboard.app import app
from aurex.adapters.web3_adapter import Web3WalletAdapter, WEB3_ADAPTER


def test_web3_adapter_methods(tmp_path):
    config_file = tmp_path / "web3_test.json"
    adapter = Web3WalletAdapter(config_path=config_file)
    
    summary = adapter.get_summary()
    assert summary["connected"] is False
    assert summary["address"] == ""
    assert "chain_id" in summary

    # Test connect
    connected_data = adapter.connect_wallet(
        address="0x71C8364420A96B35f9040000A14e63D54244013d",
        chain_id="0xa4b1",
        balance_eth=0.8521,
        balance_usdc=2500.0
    )
    assert connected_data["connected"] is True
    assert connected_data["short_address"] == "0x71C8...013d"
    assert connected_data["chain_name"] == "Arbitrum One"
    assert connected_data["balance_eth"] == 0.8521

    # Test disconnect
    adapter.disconnect_wallet()
    summary_after = adapter.get_summary()
    assert summary_after["connected"] is False
    assert summary_after["address"] == ""


def test_web3_endpoints():
    client = TestClient(app)
    
    # 1. Connect endpoint
    res_connect = client.post("/api/web3/connect", json={
        "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "chain_id": "0x1",
        "balance_eth": 12.45,
        "balance_usdc": 10000.0
    })
    assert res_connect.status_code == 200
    conn_data = res_connect.json()
    assert conn_data["status"] == "CONNECTED"
    assert conn_data["wallet"]["connected"] is True
    assert conn_data["wallet"]["chain_name"] == "Ethereum Mainnet"

    # 2. Status endpoint
    res_status = client.get("/api/web3/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["connected"] is True
    assert status_data["address"] == "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

    # 3. Disconnect endpoint
    res_disc = client.post("/api/web3/disconnect")
    assert res_disc.status_code == 200
    assert res_disc.json()["status"] == "DISCONNECTED"

    # Reconnect for persistent test consistency
    client.post("/api/web3/connect", json={
        "address": "0x71C8364420A96B35f9040000A14e63D54244013d",
        "chain_id": "0xa4b1",
        "balance_eth": 0.54,
        "balance_usdc": 1200.0
    })


def test_chat_with_metamask_query():
    client = TestClient(app)
    # Ensure wallet is connected
    client.post("/api/web3/connect", json={
        "address": "0x71C8364420A96B35f9040000A14e63D54244013d",
        "chain_id": "0xa4b1",
        "balance_eth": 0.54,
        "balance_usdc": 1200.0
    })

    res = client.post("/api/chat", json={"message": "Bagaimanakah status dompet MetaMask dan baki Web3 kita?"})
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert "MetaMask" in data["reply"] or "Web3" in data["reply"]
