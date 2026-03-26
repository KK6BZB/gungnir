"""Message framing: encode, decode, chunk, CRC for the Gungnir protocol.

Frame format:
    GUNGNIR:<tx_id>:<seq>/<total>:<payload>:<crc8>

END frame (uncompressed):
    GUNGNIR:<tx_id>:END:<crc32_of_full_tx>

END frame (compressed):
    GUNGNIR:<tx_id>:ENDZ:<crc32_of_full_tx>

ACK frame:
    GUNGNIR:<tx_id>:ACK:<first_8_chars_of_txid>

NAK frame:
    GUNGNIR:<tx_id>:NAK:<error_code>
"""

import os
import struct
import zlib

from config import PROTOCOL_ID, TX_ID_LENGTH, MAX_PAYLOAD_PER_FRAME, COMPRESS


def generate_tx_id() -> str:
    """Generate a random 4-char hex session ID."""
    return os.urandom(TX_ID_LENGTH // 2).hex()


def crc8(data: bytes) -> int:
    """Compute CRC-8/MAXIM over data bytes."""
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x31
            else:
                crc <<= 1
            crc &= 0xFF
    return crc


def crc32(data: bytes) -> str:
    """Compute CRC32 of data, return as 8-char hex string."""
    return format(zlib.crc32(data) & 0xFFFFFFFF, '08x')


def chunk_payload(base64_str: str, chunk_size: int = MAX_PAYLOAD_PER_FRAME) -> list[str]:
    """Split base64 string into chunks of chunk_size characters."""
    return [base64_str[i:i + chunk_size] for i in range(0, len(base64_str), chunk_size)]


def encode_frame(tx_id: str, seq: int, total: int, payload: str) -> str:
    """Encode a single data frame.

    Returns: GUNGNIR:<tx_id>:<seq>/<total>:<payload>:<crc8>
    """
    crc = crc8(payload.encode("ascii"))
    return f"{PROTOCOL_ID}:{tx_id}:{seq:02d}/{total:02d}:{payload}:{crc:02x}"


def encode_end_frame(tx_id: str, raw_tx_bytes: bytes, compressed: bool = False) -> str:
    """Encode the END frame with full CRC32.

    Uses ENDZ marker if payload was compressed, so gateway knows to decompress.
    CRC32 is always computed on the original uncompressed raw tx bytes.

    Returns: GUNGNIR:<tx_id>:END:<crc32>  or  GUNGNIR:<tx_id>:ENDZ:<crc32>
    """
    checksum = crc32(raw_tx_bytes)
    marker = "ENDZ" if compressed else "END"
    return f"{PROTOCOL_ID}:{tx_id}:{marker}:{checksum}"


def encode_ack_frame(tx_id: str, txid: str) -> str:
    """Encode an ACK frame with first 8 chars of the broadcast TXID.

    Returns: GUNGNIR:<tx_id>:ACK:<txid_prefix>
    """
    return f"{PROTOCOL_ID}:{tx_id}:ACK:{txid[:8]}"


def encode_nak_frame(tx_id: str, error_code: str) -> str:
    """Encode a NAK frame.

    Error codes: CRC, INV, NET, INC
    Returns: GUNGNIR:<tx_id>:NAK:<error_code>
    """
    return f"{PROTOCOL_ID}:{tx_id}:NAK:{error_code}"


def parse_frame(text: str) -> dict | None:
    """Parse a raw frame string into its components.

    Returns dict with keys depending on frame type:
        data:  {type: "data", tx_id, seq, total, payload, crc8}
        end:   {type: "end", tx_id, crc32}
        ack:   {type: "ack", tx_id, txid_prefix}
        nak:   {type: "nak", tx_id, error_code}

    Returns None if the string is not a valid Gungnir frame.
    """
    text = text.strip()
    if not text.startswith(PROTOCOL_ID + ":"):
        return None

    parts = text[len(PROTOCOL_ID) + 1:]  # everything after "GUNGNIR:"

    # Try END frame: <tx_id>:END:<crc32>
    tokens = parts.split(":")
    if len(tokens) < 2:
        return None

    tx_id = tokens[0]

    if tokens[1] in ("END", "ENDZ") and len(tokens) == 3:
        return {"type": "end", "tx_id": tx_id, "crc32": tokens[2], "compressed": tokens[1] == "ENDZ"}

    if tokens[1] == "ACK" and len(tokens) == 3:
        return {"type": "ack", "tx_id": tx_id, "txid_prefix": tokens[2]}

    if tokens[1] == "NAK" and len(tokens) == 3:
        return {"type": "nak", "tx_id": tx_id, "error_code": tokens[2]}

    # Data frame: <tx_id>:<seq>/<total>:<payload>:<crc8>
    if len(tokens) == 4:
        seq_part = tokens[1]
        if "/" not in seq_part:
            return None
        try:
            seq_str, total_str = seq_part.split("/")
            seq = int(seq_str)
            total = int(total_str)
        except ValueError:
            return None

        payload = tokens[2]
        crc_hex = tokens[3]

        # Verify CRC8
        expected_crc = crc8(payload.encode("ascii"))
        try:
            received_crc = int(crc_hex, 16)
        except ValueError:
            return None

        return {
            "type": "data",
            "tx_id": tx_id,
            "seq": seq,
            "total": total,
            "payload": payload,
            "crc8": received_crc,
            "crc8_valid": expected_crc == received_crc,
        }

    return None


def compress_bytes(data: bytes) -> bytes:
    """Compress raw bytes with zlib (level 9 — max compression for minimum airtime)."""
    return zlib.compress(data, level=9)


def decompress_bytes(data: bytes) -> bytes:
    """Decompress zlib-compressed bytes."""
    return zlib.decompress(data)


def encode_transaction(raw_tx_hex: str, compress: bool | None = None) -> tuple[str, list[str], str]:
    """Encode a full raw transaction into Gungnir frames.

    Args:
        raw_tx_hex: The raw signed transaction as a hex string.
        compress: Whether to zlib-compress before encoding. Defaults to config.COMPRESS.

    Returns:
        (tx_id, data_frames, end_frame)
        where data_frames is a list of frame strings and end_frame is the END frame.
    """
    import base64

    if compress is None:
        compress = COMPRESS

    raw_bytes = bytes.fromhex(raw_tx_hex)

    # Optionally compress — only use if it actually saves space
    used_compression = False
    if compress:
        compressed = compress_bytes(raw_bytes)
        if len(compressed) < len(raw_bytes):
            encode_bytes = compressed
            used_compression = True
        else:
            encode_bytes = raw_bytes
    else:
        encode_bytes = raw_bytes

    b64 = base64.b64encode(encode_bytes).decode("ascii")

    tx_id = generate_tx_id()
    chunks = chunk_payload(b64)
    total = len(chunks)

    frames = []
    for i, chunk in enumerate(chunks, start=1):
        frames.append(encode_frame(tx_id, i, total, chunk))

    # CRC32 is always on the original raw bytes (not compressed)
    end = encode_end_frame(tx_id, raw_bytes, compressed=used_compression)

    return tx_id, frames, end
