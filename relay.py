"""Gungnir Relay Mode — store-and-forward digipeater for GUNGNIR frames.

A relay node has NO internet. It receives GUNGNIR frames from a sender (or
another relay), buffers them, and re-transmits toward the next hop — either
another relay or the final gateway.

This extends Gungnir's range through multi-hop chains:

    Sender --HF--> Relay --HF--> Relay --HF--> Gateway --internet--> Bitcoin Network

The relay doesn't decode, decompress, or validate the transaction contents.
It just passes frames forward and ACKs/NAKs back. A dumb pipe with a callsign.
"""

import time
import logging
from datetime import datetime

import config
from config import VERSION, PROTOCOL_ID, FRAME_TIMEOUT_SECONDS, RIG_PROFILES
from framing import parse_frame
from js8call_api import JS8CallAPI, extract_directed_text

log = logging.getLogger("gungnir.relay")


class RelayBuffer:
    """Buffer frames from a sender, then re-transmit to next hop."""

    def __init__(self):
        # key: (from_callsign, tx_id) -> list of raw frame strings in order received
        self.sessions = {}
        self.timestamps = {}

    def add_frame(self, from_call: str, tx_id: str, raw_frame: str):
        key = (from_call, tx_id)
        if key not in self.sessions:
            self.sessions[key] = []
            self.timestamps[key] = datetime.now()
        self.sessions[key].append(raw_frame)

    def get_frames(self, from_call: str, tx_id: str) -> list[str]:
        return self.sessions.get((from_call, tx_id), [])

    def remove(self, from_call: str, tx_id: str):
        key = (from_call, tx_id)
        self.sessions.pop(key, None)
        self.timestamps.pop(key, None)

    def cleanup_expired(self):
        now = datetime.now()
        expired = []
        for key, ts in self.timestamps.items():
            if (now - ts).total_seconds() > FRAME_TIMEOUT_SECONDS:
                expired.append(key)
        for key in expired:
            log.info(f"Expiring relay buffer: {key}")
            del self.sessions[key]
            del self.timestamps[key]


def run_relay(
    my_callsign: str,
    next_hop: str,
    js8: JS8CallAPI,
    rig: str | None = None,
):
    """Run the relay listener loop.

    Listens for GUNGNIR frames directed to this station, buffers them,
    and re-transmits to the next hop. ACK/NAK from downstream are relayed
    back to the original sender.

    Args:
        my_callsign: This relay station's callsign.
        next_hop: The next station's callsign (relay or gateway).
        js8: Connected JS8CallAPI instance.
        rig: Rig thermal profile name.
    """
    rig_key = rig or config.DEFAULT_RIG
    profile = RIG_PROFILES.get(rig_key, RIG_PROFILES[config.DEFAULT_RIG])
    cooldown = profile["cooldown"]
    max_cont = profile["max_continuous"]
    long_break = profile["long_break"]

    print(f"\nGungnir Relay v{VERSION} -- Store-and-Forward Digipeater")
    print("=" * 58)
    print(f"  Callsign:  {my_callsign}")
    print(f"  Next hop:  {next_hop}")
    print(f"  Rig:       {profile['name']}")
    print(f"  Cooldown:  {cooldown}s between frames")
    print(f"  Status:    LISTENING")
    print()

    buf = RelayBuffer()
    # Track which sender originated each tx_id so we can route ACKs back
    # key: tx_id -> from_callsign (the station that sent TO us)
    origin_map = {}
    last_cleanup = time.time()

    while True:
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

        if not text.startswith(PROTOCOL_ID + ":"):
            continue

        parsed = parse_frame(text)
        if parsed is None:
            log.warning(f"Unparseable frame from {from_call}: {text[:80]}")
            continue

        tx_id = parsed["tx_id"]
        ts = datetime.now().strftime("%H:%M:%S")

        # --- ACK/NAK from downstream (gateway or next relay) — route back to sender ---
        if parsed["type"] in ("ack", "nak"):
            origin = origin_map.get(tx_id)
            if origin:
                direction = "ACK" if parsed["type"] == "ack" else "NAK"
                print(f"  [{ts}] Received {direction} from {from_call} for tx_id={tx_id}")
                print(f"         Relaying {direction} back to {origin}")
                js8.send_message(origin, text)
                print(f"         {direction} forwarded")
                # Clean up
                if parsed["type"] == "ack":
                    buf.remove(origin, tx_id)
                    origin_map.pop(tx_id, None)
                print()
            else:
                print(f"  [{ts}] Received {parsed['type'].upper()} for unknown tx_id={tx_id}, ignoring")
            continue

        # --- Data or END frame from sender — buffer and forward ---
        if parsed["type"] == "data":
            seq = parsed["seq"]
            total = parsed["total"]
            crc_ok = "OK" if parsed["crc8_valid"] else "CRC FAIL"
            print(f"  [{ts}] Received chunk {seq}/{total} from {from_call} -- tx_id={tx_id} {crc_ok}")

            buf.add_frame(from_call, tx_id, text)
            origin_map[tx_id] = from_call

        elif parsed["type"] == "end":
            print(f"  [{ts}] Received END from {from_call} -- tx_id={tx_id}")
            buf.add_frame(from_call, tx_id, text)
            origin_map[tx_id] = from_call

            # All frames received (including END) — forward the whole batch to next hop
            frames = buf.get_frames(from_call, tx_id)
            total_frames = len(frames)

            print(f"         Forwarding {total_frames} frames to {next_hop}...")
            print()

            consecutive = 0
            for i, frame in enumerate(frames, start=1):
                p = parse_frame(frame)
                if p and p["type"] == "data":
                    label = f"chunk {p['seq']}/{p['total']}"
                elif p and p["type"] == "end":
                    label = "END"
                else:
                    label = "frame"

                print(f"  [{datetime.now().strftime('%H:%M:%S')}] TX -> {next_hop}: {label}")
                js8.send_message(next_hop, frame)
                consecutive += 1

                if i < total_frames:
                    if consecutive >= max_cont and long_break > 0:
                        print(f"         ** Long break {long_break}s **")
                        time.sleep(long_break)
                        consecutive = 0
                    elif cooldown > 0:
                        time.sleep(cooldown)

            print()
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] All frames forwarded. Waiting for ACK from {next_hop}...")
            print()
