"""Tests for Gungnir message framing — encode, decode, chunk, CRC round-trips."""

import sys
import os
import base64

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framing import (
    generate_tx_id,
    crc8,
    crc32,
    chunk_payload,
    encode_frame,
    encode_end_frame,
    encode_ack_frame,
    encode_nak_frame,
    parse_frame,
    encode_transaction,
    decompress_bytes,
)
from config import MAX_PAYLOAD_PER_FRAME


# Minimal valid SegWit transaction (version 2, simplified)
# This is a synthetic but structurally plausible raw tx hex
SAMPLE_TX_HEX = (
    "02000000"  # version
    "0001"      # segwit marker + flag
    "01"        # input count
    "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"  # prev txid
    "00000000"  # prev index
    "00"        # scriptSig length (empty for segwit)
    "ffffffff"  # sequence
    "02"        # output count
    "e803000000000000"  # value (1000 sats)
    "16" "0014" "aabbccddaabbccddaabbccddaabbccddaabbccdd"  # P2WPKH output
    "e803000000000000"  # value (1000 sats)
    "16" "0014" "11223344112233441122334411223344aabbccdd"  # P2WPKH output
    "00"        # witness (empty placeholder)
    "00000000"  # locktime
)


class TestCRC:
    def test_crc8_deterministic(self):
        data = b"hello"
        assert crc8(data) == crc8(data)

    def test_crc8_different_data(self):
        assert crc8(b"hello") != crc8(b"world")

    def test_crc8_range(self):
        result = crc8(b"test data")
        assert 0 <= result <= 255

    def test_crc32_deterministic(self):
        data = b"hello"
        assert crc32(data) == crc32(data)

    def test_crc32_format(self):
        result = crc32(b"test")
        assert len(result) == 8
        assert all(c in "0123456789abcdef" for c in result)


class TestChunking:
    def test_chunk_small(self):
        chunks = chunk_payload("abc", chunk_size=50)
        assert chunks == ["abc"]

    def test_chunk_exact(self):
        data = "a" * 50
        chunks = chunk_payload(data, chunk_size=50)
        assert chunks == [data]

    def test_chunk_splits(self):
        data = "a" * 120
        chunks = chunk_payload(data, chunk_size=50)
        assert len(chunks) == 3
        assert chunks[0] == "a" * 50
        assert chunks[1] == "a" * 50
        assert chunks[2] == "a" * 20

    def test_chunk_reassemble(self):
        data = "abcdefghijklmnopqrstuvwxyz" * 5
        chunks = chunk_payload(data, chunk_size=10)
        assert "".join(chunks) == data


class TestFrameEncoding:
    def test_encode_data_frame(self):
        frame = encode_frame("a7f2", 1, 3, "SGVsbG8gV29ybGQ=")
        assert frame.startswith("GUNGNIR:a7f2:01/03:SGVsbG8gV29ybGQ=:")
        # CRC8 should be 2 hex chars
        parts = frame.split(":")
        assert len(parts[-1]) == 2

    def test_encode_end_frame(self):
        raw = bytes.fromhex("deadbeef")
        frame = encode_end_frame("a7f2", raw)
        assert frame.startswith("GUNGNIR:a7f2:END:")
        assert len(frame.split(":")[-1]) == 8  # CRC32 is 8 hex chars

    def test_encode_ack_frame(self):
        frame = encode_ack_frame("a7f2", "3a4b5c6d7e8f1234")
        assert frame == "GUNGNIR:a7f2:ACK:3a4b5c6d"

    def test_encode_nak_frame(self):
        frame = encode_nak_frame("a7f2", "CRC")
        assert frame == "GUNGNIR:a7f2:NAK:CRC"


class TestFrameParsing:
    def test_parse_data_frame(self):
        frame = encode_frame("a7f2", 2, 5, "SGVsbG8=")
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed["type"] == "data"
        assert parsed["tx_id"] == "a7f2"
        assert parsed["seq"] == 2
        assert parsed["total"] == 5
        assert parsed["payload"] == "SGVsbG8="
        assert parsed["crc8_valid"] is True

    def test_parse_end_frame(self):
        raw = bytes.fromhex("cafebabe")
        frame = encode_end_frame("b3c1", raw)
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed["type"] == "end"
        assert parsed["tx_id"] == "b3c1"
        assert parsed["crc32"] == crc32(raw)

    def test_parse_ack_frame(self):
        frame = encode_ack_frame("d4e5", "1234abcd5678ef01")
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed["type"] == "ack"
        assert parsed["tx_id"] == "d4e5"
        assert parsed["txid_prefix"] == "1234abcd"

    def test_parse_nak_frame(self):
        frame = encode_nak_frame("f6a7", "NET")
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed["type"] == "nak"
        assert parsed["error_code"] == "NET"

    def test_parse_invalid(self):
        assert parse_frame("not a frame") is None
        assert parse_frame("") is None
        assert parse_frame("GUNGNIR:") is None

    def test_parse_corrupted_crc(self):
        frame = encode_frame("a7f2", 1, 1, "SGVsbG8=")
        # Corrupt the CRC by changing last char
        corrupted = frame[:-1] + ("0" if frame[-1] != "0" else "1")
        parsed = parse_frame(corrupted)
        # Should still parse but flag invalid CRC
        if parsed and parsed["type"] == "data":
            assert parsed["crc8_valid"] is False


class TestRoundTrip:
    def _roundtrip(self, raw_hex, compress=True):
        """Helper: encode -> parse frames -> reassemble -> decompress -> verify."""
        raw_bytes = bytes.fromhex(raw_hex)

        tx_id, data_frames, end_frame = encode_transaction(raw_hex, compress=compress)

        # Parse all data frames
        chunks = {}
        for frame_str in data_frames:
            parsed = parse_frame(frame_str)
            assert parsed is not None
            assert parsed["type"] == "data"
            assert parsed["crc8_valid"] is True
            chunks[parsed["seq"]] = parsed["payload"]

        # Reassemble
        total = len(data_frames)
        b64_reassembled = "".join(chunks[i] for i in range(1, total + 1))
        decoded_bytes = base64.b64decode(b64_reassembled)

        # Decompress if END frame says so
        end_parsed = parse_frame(end_frame)
        assert end_parsed is not None
        assert end_parsed["type"] == "end"

        if end_parsed.get("compressed"):
            final_bytes = decompress_bytes(decoded_bytes)
        else:
            final_bytes = decoded_bytes

        assert final_bytes == raw_bytes
        assert end_parsed["crc32"] == crc32(raw_bytes)
        return data_frames, end_parsed

    def test_full_encode_decode_roundtrip(self):
        """The core test: encode a tx, parse every frame, reassemble, verify match."""
        self._roundtrip(SAMPLE_TX_HEX)

    def test_roundtrip_no_compression(self):
        """Round-trip without compression."""
        self._roundtrip(SAMPLE_TX_HEX, compress=False)

    def test_single_chunk_tx(self):
        """Minimal tx that fits in one chunk."""
        raw_hex = "01000000" + "aa" * 60  # 64 bytes, version 1
        tx_id, frames, end = encode_transaction(raw_hex)
        assert len(frames) >= 1

    def test_large_tx(self):
        """Larger transaction with many chunks."""
        # 500 bytes of random-ish data (high entropy = less compressible)
        import os
        raw_hex = "02000000" + os.urandom(496).hex()
        frames, end_parsed = self._roundtrip(raw_hex)
        assert len(frames) >= 5  # even compressed, 500 random bytes needs several chunks

    def test_large_tx_no_compression(self):
        """Large tx without compression needs many chunks."""
        raw_hex = "02000000" + "bb" * 496
        tx_id, frames, end = encode_transaction(raw_hex, compress=False)
        assert len(frames) > 10
        for frame in frames:
            parsed = parse_frame(frame)
            assert parsed is not None
            assert parsed["crc8_valid"] is True


class TestTxId:
    def test_tx_id_length(self):
        tid = generate_tx_id()
        assert len(tid) == 4

    def test_tx_id_hex(self):
        tid = generate_tx_id()
        assert all(c in "0123456789abcdef" for c in tid)

    def test_tx_id_randomness(self):
        ids = {generate_tx_id() for _ in range(100)}
        # Should get many unique IDs (collisions extremely unlikely)
        assert len(ids) > 90
