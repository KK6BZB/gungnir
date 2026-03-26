#!/usr/bin/env python3
"""Gungnir Loopback Demo — full sender->gateway flow, no radio needed.

Simulates the complete protocol: chunking, framing, CRC verification,
reassembly, and ACK — all on localhost with simulated propagation delays.

Usage:
    python demo_loopback.py

Optional:
    python demo_loopback.py --sound    Enable simulated JS8Call TX audio
"""

import sys
import os
import time
import base64
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import VERSION
from framing import (
    encode_transaction, parse_frame, encode_ack_frame, crc32,
    decompress_bytes,
)
from config import RIG_PROFILES, JS8_SPEEDS

SENDER_CALL = "KK6BZB"
GATEWAY_CALL = "KE7ABC"

# A structurally valid testnet transaction
SAMPLE_TX = (
    "02000000"
    "0001"
    "01"
    "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    "00000000"
    "00"
    "ffffffff"
    "02"
    "e803000000000000"
    "16" "0014" "aabbccddaabbccddaabbccddaabbccddaabbccdd"
    "e803000000000000"
    "16" "0014" "11223344112233441122334411223344aabbccdd"
    "00"
    "00000000"
)

USE_SOUND = "--sound" in sys.argv


def beep(freq=800, duration_ms=100):
    """Play a beep on Windows (no-op on other platforms)."""
    if not USE_SOUND:
        return
    try:
        import winsound
        winsound.Beep(freq, duration_ms)
    except Exception:
        pass


def simulate_tx_tone(duration=1.0):
    """Simulate the JS8Call transmission tone."""
    if not USE_SOUND:
        return
    try:
        import winsound
        # JS8Call uses ~1000-2500 Hz FSK-like tones
        steps = int(duration * 10)
        for i in range(steps):
            freq = 1000 + (i % 5) * 300  # wobble between 1000-2200 Hz
            winsound.Beep(freq, 80)
    except Exception:
        pass


def print_header():
    print()
    print("  " + "=" * 58)
    print(f"  Gungnir v{VERSION} — Loopback Demo (no radio)")
    print("  " + "=" * 58)
    print()
    print(f"  Sender:   {SENDER_CALL} (off-grid, Tucson AZ)")
    print(f"  Gateway:  {GATEWAY_CALL} (internet relay)")
    print(f"  Band:     40m / 7.078 MHz (simulated)")
    print(f"  Mode:     JS8Call Normal")
    print(f"  TX size:  {len(bytes.fromhex(SAMPLE_TX))} bytes")
    print(f"  Network:  testnet (demo — no actual broadcast)")
    if USE_SOUND:
        print(f"  Audio:    ON (simulated TX tones)")
    print()


def simulate_propagation(frame_text, from_call, to_call, frame_num=None, total_frames=None):
    """Simulate a single frame being transmitted over the air."""
    label = ""
    if frame_num and total_frames:
        label = f"chunk {frame_num}/{total_frames}"
    elif "END" in frame_text:
        label = "END frame"
    elif "ACK" in frame_text:
        label = "ACK"

    # Sender TX
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] {from_call} TX: {label}")
    print(f"           {frame_text[:70]}{'...' if len(frame_text) > 70 else ''}")

    # Simulated TX tone
    simulate_tx_tone(0.5)

    # Propagation delay
    sys.stdout.write(f"           ~~~ propagating ~~~")
    sys.stdout.flush()
    time.sleep(0.8)
    print()

    # Gateway RX
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] {to_call} RX: {label} received")
    beep(600, 50)
    print()


def main():
    print_header()

    raw_bytes = bytes.fromhex(SAMPLE_TX)

    # === Show compression savings ===
    print(f"  --- COMPRESSION ---")
    # Uncompressed baseline
    _, frames_raw, _ = encode_transaction(SAMPLE_TX, compress=False)
    # Compressed
    tx_id, data_frames, end_frame = encode_transaction(SAMPLE_TX, compress=True)
    num_chunks_raw = len(frames_raw)
    num_chunks = len(data_frames)

    end_parsed = parse_frame(end_frame)
    is_compressed = end_parsed.get("compressed", False)

    print(f"  Original:     {len(raw_bytes)} bytes")
    if is_compressed:
        import zlib
        compressed_size = len(zlib.compress(raw_bytes, level=9))
        savings_pct = (1 - compressed_size / len(raw_bytes)) * 100
        print(f"  Compressed:   {compressed_size} bytes ({savings_pct:.0f}% smaller)")
        print(f"  Chunks:       {num_chunks_raw} (raw) -> {num_chunks} (compressed)")
    else:
        print(f"  Compression:  skipped (wouldn't save space on this tx)")
        print(f"  Chunks:       {num_chunks}")
    print()

    # === SENDER: Encode ===
    demo_rig = RIG_PROFILES["g90"]
    print(f"  --- SENDER ({SENDER_CALL}) ---")
    print(f"  Session ID: {tx_id}")
    print(f"  Frames:     {num_chunks} data + 1 END")
    print(f"  Rig:        {demo_rig['name']} ({demo_rig['cooldown']}s cooldown, break every {demo_rig['max_continuous']} frames)")
    print(f"  CRC32:      {crc32(raw_bytes)}")
    print()

    time.sleep(1)

    # === TRANSMIT DATA FRAMES ===
    print(f"  --- TRANSMISSION START ---")
    print()

    gateway_chunks = {}
    airtime_per_frame = 15  # seconds at JS8Call Normal speed

    for i, frame in enumerate(data_frames, start=1):
        # Sender transmits
        simulate_propagation(frame, SENDER_CALL, GATEWAY_CALL, i, num_chunks)

        # Gateway processes
        parsed = parse_frame(frame)
        if parsed and parsed["type"] == "data":
            crc_status = "CRC8 OK" if parsed["crc8_valid"] else "CRC8 FAIL"
            gateway_chunks[parsed["seq"]] = parsed["payload"]
            print(f"           Gateway: stored chunk {parsed['seq']}/{parsed['total']} — {crc_status}")

        # TX cooldown between frames
        if i < num_chunks:
            print(f"           [{SENDER_CALL} cooling down {demo_rig['cooldown']}s — letting finals rest]")
            print()
            time.sleep(0.3)  # abbreviated for demo
        else:
            print()

    # Cooldown before END
    print(f"           [{SENDER_CALL} cooling down {demo_rig['cooldown']}s]")
    time.sleep(0.3)
    print()

    # === TRANSMIT END FRAME ===
    simulate_propagation(end_frame, SENDER_CALL, GATEWAY_CALL)

    print(f"           Gateway: {'ENDZ' if is_compressed else 'END'} received — verifying integrity...")
    time.sleep(0.5)

    # === GATEWAY: Reassemble ===
    print()
    print(f"  --- GATEWAY ({GATEWAY_CALL}) REASSEMBLY ---")
    print()

    # Check completeness
    total = num_chunks
    missing = [i for i in range(1, total + 1) if i not in gateway_chunks]
    if missing:
        print(f"  MISSING chunks: {missing}")
        return

    print(f"  All {total} chunks received")

    # Reassemble
    b64_full = "".join(gateway_chunks[i] for i in range(1, total + 1))
    decoded_bytes = base64.b64decode(b64_full)

    # Decompress if needed
    if is_compressed:
        raw_result = decompress_bytes(decoded_bytes)
        print(f"  Decompressed:   {len(decoded_bytes)} -> {len(raw_result)} bytes")
    else:
        raw_result = decoded_bytes
        print(f"  Reassembled:    {len(raw_result)} bytes")

    # Verify CRC32 (against original uncompressed bytes)
    computed_crc = crc32(raw_result)
    expected_crc = end_parsed["crc32"]
    match = computed_crc == expected_crc
    print(f"  CRC32 expected: {expected_crc}")
    print(f"  CRC32 computed: {computed_crc}")
    print(f"  CRC32 match:    {'YES' if match else 'NO — MISMATCH!'}")

    if not match:
        print("  ABORTING — integrity check failed")
        return

    # Verify data matches original
    if raw_result.hex() == SAMPLE_TX.lower():
        print(f"  Byte-perfect:   YES — decoded tx matches original")
    print()

    # === GATEWAY: Broadcast ===
    print(f"  --- BROADCAST ---")
    print()
    fake_txid = hashlib.sha256(raw_result).hexdigest()
    print(f"  [DEMO] Would POST to: https://mempool.space/testnet/api/tx")
    print(f"  [DEMO] TXID: {fake_txid}")
    beep(1000, 200)
    print()

    time.sleep(0.5)

    # === GATEWAY: Send ACK ===
    ack_frame = encode_ack_frame(tx_id, fake_txid)
    print(f"  --- ACK ---")
    print()
    simulate_propagation(ack_frame, GATEWAY_CALL, SENDER_CALL)

    ack_parsed = parse_frame(ack_frame)
    print(f"           Sender: ACK received! TXID prefix: {ack_parsed['txid_prefix']}")
    beep(1200, 300)

    # === TIMING SUMMARY ===
    print()
    print("  " + "=" * 58)
    print("  TRANSACTION RELAYED SUCCESSFULLY")
    print("  " + "=" * 58)
    print()
    print(f"  {SENDER_CALL} signed a Bitcoin transaction with no internet.")
    print(f"  {GATEWAY_CALL} relayed it to the Bitcoin network over HF radio.")
    print()

    # Real-world timing estimates per rig
    total_frames = num_chunks + 2  # data + END + ACK
    total_frames_raw = num_chunks_raw + 2
    spd = JS8_SPEEDS["normal"]

    def _estimate(rig_key, n_chunks, speed_sec):
        p = RIG_PROFILES[rig_key]
        frames = n_chunks + 2  # data + END + ACK
        tx_sec = frames * speed_sec
        # Count cooldowns: between each data frame + before END = n_chunks breaks
        # Plus long breaks: every max_continuous frames
        short_breaks = n_chunks  # cooldowns between data frames + before END
        long_breaks = max(0, (n_chunks - 1) // p["max_continuous"])
        # Long breaks replace a short break, so subtract those
        short_breaks -= long_breaks
        rest_sec = (short_breaks * p["cooldown"]) + (long_breaks * p["long_break"])
        wall = tx_sec + rest_sec
        return tx_sec, rest_sec, wall

    if is_compressed:
        raw_tx_time = total_frames_raw * spd
        print(f"  Without compression: {num_chunks_raw} data + END + ACK = {raw_tx_time}s TX")
        print(f"  With compression:    {num_chunks} data + END + ACK = {total_frames * spd}s TX")
        print(f"  Saved:               {num_chunks_raw - num_chunks} frames / {(total_frames_raw - total_frames) * spd}s")
        print()

    print(f"  --- Wall Time by Rig (JS8Call Normal, {spd}s/frame) ---")
    print(f"  {'Rig':<26} {'TX':>5}  {'Rest':>5}  {'Total':>7}  Duty Cycle")
    print(f"  {'-'*26} {'-'*5}  {'-'*5}  {'-'*7}  {'-'*12}")

    for rig_key in ["g90", "ft857", "base", "none"]:
        p = RIG_PROFILES[rig_key]
        tx_sec, rest_sec, wall = _estimate(rig_key, num_chunks, spd)
        wall_str = f"{wall // 60}m {wall % 60:02d}s" if wall >= 60 else f"{wall}s"
        duty = tx_sec / wall * 100 if wall > 0 else 100
        print(f"  {p['name']:<26} {tx_sec:>4}s  {rest_sec:>4}s  {wall_str:>7}  {duty:.0f}%")

    print()
    print(f"  Xiegu G90:  10s cooldown + 30s break every 3 frames")
    print(f"              {RIG_PROFILES['g90']['max_power_note']}")
    print(f"  Yaesu 857:  5s cooldown + 15s break every 6 frames")
    print(f"              {RIG_PROFILES['ft857']['max_power_note']}")
    print()

    # Turbo speed comparison
    turbo = JS8_SPEEDS["turbo"]
    tx_g90_t, rest_g90_t, wall_g90_t = _estimate("g90", num_chunks, turbo)
    tx_857_t, rest_857_t, wall_857_t = _estimate("ft857", num_chunks, turbo)
    print(f"  --- Turbo Speed ({turbo}s/frame, strong signal) ---")
    print(f"  G90:   {wall_g90_t}s total  |  FT-857: {wall_857_t}s total")
    print()

    if not USE_SOUND:
        print(f"  Tip: run with --sound to hear simulated TX tones")
        print()


if __name__ == "__main__":
    main()
