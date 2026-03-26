"""Gungnir Gateway Mode — listen for transactions, reassemble, and broadcast to Bitcoin network."""

import time
import base64
import logging
from datetime import datetime

from config import VERSION, FRAME_TIMEOUT_SECONDS, PROTOCOL_ID
from framing import parse_frame, crc32, encode_ack_frame, encode_nak_frame, decompress_bytes
from js8call_api import JS8CallAPI, extract_directed_text
from broadcast import broadcast_via_mempool, broadcast_via_node, BroadcastError

log = logging.getLogger("gungnir.gateway")


class TransactionBuffer:
    """In-memory buffer for in-progress transaction reassembly."""

    def __init__(self):
        self.sessions = {}  # key: (from_callsign, tx_id)

    def add_chunk(self, from_call: str, tx_id: str, seq: int, total: int, payload: str, crc8_valid: bool):
        """Store a received chunk."""
        key = (from_call, tx_id)
        if key not in self.sessions:
            self.sessions[key] = {
                "total": total,
                "chunks": {},
                "received_at": datetime.now(),
                "crc8_verified": {},
            }

        session = self.sessions[key]
        session["chunks"][seq] = payload
        session["crc8_verified"][seq] = crc8_valid
        session["total"] = total

    def is_complete(self, from_call: str, tx_id: str) -> bool:
        """Check if all chunks have been received."""
        key = (from_call, tx_id)
        session = self.sessions.get(key)
        if not session:
            return False
        return len(session["chunks"]) == session["total"]

    def reassemble(self, from_call: str, tx_id: str) -> str | None:
        """Reassemble chunks into the full base64 string.

        Returns None if incomplete or any CRC8 failed.
        """
        key = (from_call, tx_id)
        session = self.sessions.get(key)
        if not session:
            return None

        total = session["total"]
        chunks = session["chunks"]

        # Check completeness
        for i in range(1, total + 1):
            if i not in chunks:
                return None

        # Check all CRC8 values passed
        for i in range(1, total + 1):
            if not session["crc8_verified"].get(i, False):
                return None

        # Reassemble in order
        return "".join(chunks[i] for i in range(1, total + 1))

    def remove(self, from_call: str, tx_id: str):
        """Remove a completed or expired session."""
        key = (from_call, tx_id)
        self.sessions.pop(key, None)

    def cleanup_expired(self):
        """Remove sessions older than FRAME_TIMEOUT_SECONDS."""
        now = datetime.now()
        expired = []
        for key, session in self.sessions.items():
            age = (now - session["received_at"]).total_seconds()
            if age > FRAME_TIMEOUT_SECONDS:
                expired.append(key)
        for key in expired:
            log.info(f"Expiring incomplete session: {key}")
            del self.sessions[key]


def run_gateway(
    my_callsign: str,
    js8: JS8CallAPI,
    testnet: bool = True,
    node_url: str | None = None,
    rpc_user: str | None = None,
    rpc_pass: str | None = None,
    no_broadcast: bool = False,
):
    """Run the gateway listener loop.

    Args:
        my_callsign: This station's callsign.
        js8: Connected JS8CallAPI instance.
        testnet: Use testnet for broadcasting.
        node_url: Optional Bitcoin Core RPC URL.
        rpc_user: Optional RPC username.
        rpc_pass: Optional RPC password.
    """
    network = "testnet" if testnet else "mainnet"
    broadcast_target = "DISABLED (no-broadcast mode)" if no_broadcast else (node_url or "mempool.space API")

    print(f"\nGungnir Gateway v{VERSION} — Listening for transactions")
    print("=" * 58)
    print(f"  Callsign:  {my_callsign}")
    print(f"  Network:   {network}")
    print(f"  Broadcast: {broadcast_target}")
    print(f"  Status:    LISTENING")
    print()

    buf = TransactionBuffer()
    last_cleanup = time.time()

    while True:
        # Periodic cleanup of expired sessions
        if time.time() - last_cleanup > 60:
            buf.cleanup_expired()
            last_cleanup = time.time()

        msg = js8.listen(timeout=5.0)
        if msg is None:
            continue

        directed = extract_directed_text(msg)
        if directed is None:
            continue

        from_call, to_call, text = directed

        # Only process messages directed to us
        if to_call.upper() != my_callsign.upper():
            continue

        # Must be a Gungnir frame
        if not text.startswith(PROTOCOL_ID + ":"):
            continue

        parsed = parse_frame(text)
        if parsed is None:
            log.warning(f"Unparseable Gungnir frame from {from_call}: {text[:80]}")
            continue

        tx_id = parsed["tx_id"]
        ts = datetime.now().strftime("%H:%M:%S")

        if parsed["type"] == "data":
            seq = parsed["seq"]
            total = parsed["total"]
            crc_ok = parsed["crc8_valid"]

            buf.add_chunk(from_call, tx_id, seq, total, parsed["payload"], crc_ok)

            status = "OK" if crc_ok else "CRC FAIL"
            print(f"  [{ts}] Received frame from {from_call} — tx_id={tx_id}, "
                  f"chunk {seq}/{total} {status}")

            if not crc_ok:
                log.warning(f"CRC8 failed on chunk {seq} from {from_call}, tx_id={tx_id}")

        elif parsed["type"] == "end":
            print(f"  [{ts}] Received END frame from {from_call} — tx_id={tx_id}")

            # Check completeness
            if not buf.is_complete(from_call, tx_id):
                print(f"           Incomplete — missing chunks")
                _send_nak(js8, from_call, tx_id, "INC")
                buf.remove(from_call, tx_id)
                continue

            # Reassemble
            b64_str = buf.reassemble(from_call, tx_id)
            if b64_str is None:
                print(f"           Reassembly failed — CRC8 errors on one or more chunks")
                _send_nak(js8, from_call, tx_id, "CRC")
                buf.remove(from_call, tx_id)
                continue

            # Decode
            try:
                decoded_bytes = base64.b64decode(b64_str)
            except Exception:
                print(f"           Base64 decode failed")
                _send_nak(js8, from_call, tx_id, "INV")
                buf.remove(from_call, tx_id)
                continue

            # Decompress if sender used compression (ENDZ marker)
            if parsed.get("compressed"):
                try:
                    raw_bytes = decompress_bytes(decoded_bytes)
                    print(f"           Decompressed {len(decoded_bytes)} -> {len(raw_bytes)} bytes")
                except Exception as e:
                    print(f"           Decompression failed: {e}")
                    _send_nak(js8, from_call, tx_id, "INV")
                    buf.remove(from_call, tx_id)
                    continue
            else:
                raw_bytes = decoded_bytes

            raw_hex = raw_bytes.hex()
            print(f"           Reassembled {len(raw_bytes)} bytes")

            # Verify CRC32 (always against original uncompressed bytes)
            computed_crc = crc32(raw_bytes)
            if computed_crc != parsed["crc32"]:
                print(f"           CRC32 MISMATCH: expected {parsed['crc32']}, got {computed_crc}")
                _send_nak(js8, from_call, tx_id, "CRC")
                buf.remove(from_call, tx_id)
                continue

            print(f"           CRC32 verified")

            # Broadcast
            if no_broadcast:
                import hashlib
                fake_txid = hashlib.sha256(raw_bytes).hexdigest()
                print(f"           No-broadcast mode — skipping Bitcoin broadcast")
                print(f"           Fake TXID: {fake_txid}")
                print(f"           Sending ACK to {from_call}")
                _send_ack(js8, from_call, tx_id, fake_txid)
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] ACK sent. Pipeline test successful.")
            else:
                print(f"           Broadcasting to {network}...")
                try:
                    if node_url:
                        txid = broadcast_via_node(raw_hex, node_url, rpc_user, rpc_pass)
                    else:
                        txid = broadcast_via_mempool(raw_hex, testnet=testnet)

                    print(f"           TXID: {txid}")
                    print(f"           Sending ACK to {from_call}")
                    _send_ack(js8, from_call, tx_id, txid)
                    print(f"  [{datetime.now().strftime('%H:%M:%S')}] ACK sent. Transaction relayed successfully.")

                except BroadcastError as e:
                    print(f"           Broadcast failed: {e}")
                    _send_nak(js8, from_call, tx_id, "NET")

            buf.remove(from_call, tx_id)
            print()


def _send_ack(js8: JS8CallAPI, to_call: str, tx_id: str, txid: str):
    """Send an ACK frame back to the sender."""
    frame = encode_ack_frame(tx_id, txid)
    js8.send_message(to_call, frame)


def _send_nak(js8: JS8CallAPI, to_call: str, tx_id: str, error_code: str):
    """Send a NAK frame back to the sender."""
    frame = encode_nak_frame(tx_id, error_code)
    js8.send_message(to_call, frame)
    print(f"           NAK sent: {error_code}")
