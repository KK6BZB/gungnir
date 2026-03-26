"""Gungnir Sender Mode — encode and transmit a signed Bitcoin transaction via JS8Call."""

import time
import logging

import config
from config import VERSION, MAX_CHUNKS_WARNING, PROTOCOL_ID, RIG_PROFILES
from framing import encode_transaction, parse_frame
from js8call_api import JS8CallAPI, extract_directed_text
from utils import is_valid_raw_tx

log = logging.getLogger("gungnir.sender")


def send_transaction(
    raw_tx_hex: str,
    gateway_callsign: str,
    js8: JS8CallAPI,
    testnet: bool = True,
    rig: str | None = None,
) -> dict:
    """Encode and send a raw transaction to a gateway via JS8Call.

    Args:
        raw_tx_hex: Signed raw transaction hex string.
        gateway_callsign: Destination gateway amateur callsign.
        js8: Connected JS8CallAPI instance.
        testnet: Whether this is a testnet transaction.
        rig: Rig profile name (g90, ft857, qrp, base, none). Uses config default if None.

    Returns:
        dict with keys: success (bool), txid (str|None), error (str|None)
    """
    raw_tx_hex = raw_tx_hex.strip().lower()
    network = "testnet" if testnet else "mainnet"

    # Resolve rig profile
    rig_key = rig or config.DEFAULT_RIG
    profile = RIG_PROFILES.get(rig_key, RIG_PROFILES[config.DEFAULT_RIG])
    cooldown = profile["cooldown"]
    max_cont = profile["max_continuous"]
    long_break = profile["long_break"]

    # Validate
    if not is_valid_raw_tx(raw_tx_hex):
        return {"success": False, "txid": None, "error": "Invalid raw transaction hex"}

    raw_bytes = bytes.fromhex(raw_tx_hex)
    tx_size = len(raw_bytes)

    # Encode into frames
    tx_id, data_frames, end_frame = encode_transaction(raw_tx_hex)
    num_chunks = len(data_frames)

    # Display header
    print(f"\nGungnir v{VERSION} -- Bitcoin Transaction Relay via HF Radio")
    print("=" * 58)
    print(f"  Transaction: {tx_size} bytes")
    print(f"  Chunks:      {num_chunks} frames + END")
    print(f"  Session:     tx_id={tx_id}")
    print(f"  Target:      {gateway_callsign} (gateway)")
    print(f"  Network:     {network}")
    print(f"  Rig:         {profile['name']}")
    print(f"  Duty cycle:  {cooldown}s cooldown, break every {max_cont} frames")
    print(f"  Power:       {profile['max_power_note']}")
    print()

    if num_chunks > MAX_CHUNKS_WARNING:
        print(f"  WARNING: {num_chunks} chunks -- large transaction.")
        print(f"           Consider a simpler UTXO set if possible.")
        print()

    # Send data frames with thermal management
    consecutive = 0
    for i, frame in enumerate(data_frames, start=1):
        print(f"  Sending chunk {i}/{num_chunks}...", end=" ", flush=True)
        js8.send_message(gateway_callsign, frame)
        print("queued")
        consecutive += 1

        if i < num_chunks:
            # Check if we need a long break
            if consecutive >= max_cont and long_break > 0:
                print(f"  ** Long break {long_break}s -- letting PA cool **", flush=True)
                time.sleep(long_break)
                consecutive = 0
            elif cooldown > 0:
                print(f"  Cooldown {cooldown}s...", flush=True)
                time.sleep(cooldown)

    # Cooldown before END frame
    if cooldown > 0:
        print(f"  Cooldown {cooldown}s...", flush=True)
        time.sleep(cooldown)

    # Send END frame
    print(f"  Sending END frame...", end=" ", flush=True)
    js8.send_message(gateway_callsign, end_frame)
    print("queued")
    print()

    # Wait for ACK/NAK
    print(f"  Waiting for confirmation from {gateway_callsign}...")
    result = _wait_for_ack(js8, tx_id, gateway_callsign, timeout=config.ACK_TIMEOUT_SECONDS)

    if result["success"]:
        print(f"\n  ACK received! TXID: {result['txid']}...")
        print(f"  Transaction broadcast to Bitcoin {network}.")
    elif result.get("error_code"):
        print(f"\n  NAK received -- error: {result['error_code']}")
    else:
        print(f"\n  Timeout -- no response from {gateway_callsign} within {config.ACK_TIMEOUT_SECONDS}s.")

    print()
    return result


def _wait_for_ack(js8: JS8CallAPI, tx_id: str, gateway_callsign: str, timeout: int) -> dict:
    """Listen for an ACK or NAK frame from the gateway.

    Returns:
        dict with keys: success, txid, error, error_code
    """
    deadline = time.time() + timeout

    while time.time() < deadline:
        remaining = deadline - time.time()
        msg = js8.listen(timeout=min(remaining, 10.0))

        if msg is None:
            continue

        directed = extract_directed_text(msg)
        if directed is None:
            continue

        from_call, to_call, text = directed

        # Look for Gungnir frames from the gateway
        if not text.startswith(PROTOCOL_ID + ":"):
            continue

        parsed = parse_frame(text)
        if parsed is None:
            continue

        if parsed["tx_id"] != tx_id:
            continue

        if parsed["type"] == "ack":
            return {
                "success": True,
                "txid": parsed["txid_prefix"],
                "error": None,
                "error_code": None,
            }
        elif parsed["type"] == "nak":
            return {
                "success": False,
                "txid": None,
                "error": f"Gateway rejected: {parsed['error_code']}",
                "error_code": parsed["error_code"],
            }

    return {
        "success": False,
        "txid": None,
        "error": "Timeout waiting for ACK",
        "error_code": None,
    }
