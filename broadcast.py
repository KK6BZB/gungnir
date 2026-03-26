"""Bitcoin network broadcast — mempool.space API and local node RPC."""

import logging
import requests

from config import MEMPOOL_MAINNET, MEMPOOL_TESTNET

log = logging.getLogger("gungnir.broadcast")


def broadcast_via_mempool(raw_tx_hex: str, testnet: bool = True) -> str:
    """Broadcast a raw transaction via mempool.space API.

    Args:
        raw_tx_hex: Raw signed transaction as hex string.
        testnet: Use testnet endpoint if True.

    Returns:
        The TXID string on success.

    Raises:
        BroadcastError: On any failure.
    """
    url = MEMPOOL_TESTNET if testnet else MEMPOOL_MAINNET
    log.info(f"Broadcasting to {url}")

    try:
        resp = requests.post(
            url,
            data=raw_tx_hex,
            headers={"Content-Type": "text/plain"},
            timeout=30,
        )
        if resp.status_code == 200:
            txid = resp.text.strip()
            log.info(f"Broadcast success — TXID: {txid}")
            return txid
        else:
            raise BroadcastError(f"mempool.space returned {resp.status_code}: {resp.text[:200]}")
    except requests.RequestException as e:
        raise BroadcastError(f"Network error: {e}") from e


def broadcast_via_node(raw_tx_hex: str, rpc_url: str, rpc_user: str, rpc_pass: str) -> str:
    """Broadcast via a local Bitcoin Core node's JSON-RPC.

    Args:
        raw_tx_hex: Raw signed transaction as hex string.
        rpc_url: Bitcoin Core RPC URL (e.g. http://localhost:8332).
        rpc_user: RPC username.
        rpc_pass: RPC password.

    Returns:
        The TXID string on success.

    Raises:
        BroadcastError: On any failure.
    """
    payload = {
        "jsonrpc": "1.0",
        "id": "gungnir",
        "method": "sendrawtransaction",
        "params": [raw_tx_hex],
    }

    try:
        resp = requests.post(
            rpc_url,
            json=payload,
            auth=(rpc_user, rpc_pass),
            timeout=30,
        )
        result = resp.json()
        if result.get("error"):
            raise BroadcastError(f"Node RPC error: {result['error']}")
        txid = result["result"]
        log.info(f"Broadcast via node success — TXID: {txid}")
        return txid
    except requests.RequestException as e:
        raise BroadcastError(f"Node connection error: {e}") from e


class BroadcastError(Exception):
    """Raised when transaction broadcast fails."""
    pass
