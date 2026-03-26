"""Tests for Gungnir Gateway — mock incoming frames, verify reassembly."""

import sys
import os
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framing import encode_transaction, crc32, parse_frame, decompress_bytes
from gateway import TransactionBuffer


# Same sample tx as other tests
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


class TestTransactionBuffer:
    def test_add_and_complete(self):
        buf = TransactionBuffer()
        tx_id, frames, end = encode_transaction(SAMPLE_TX)
        total = len(frames)

        for frame_str in frames:
            parsed = parse_frame(frame_str)
            buf.add_chunk("KK6BZB", tx_id, parsed["seq"], parsed["total"],
                          parsed["payload"], parsed["crc8_valid"])

        assert buf.is_complete("KK6BZB", tx_id)

    def test_incomplete(self):
        buf = TransactionBuffer()
        tx_id, frames, end = encode_transaction(SAMPLE_TX)

        # Only add first chunk
        parsed = parse_frame(frames[0])
        buf.add_chunk("KK6BZB", tx_id, parsed["seq"], parsed["total"],
                      parsed["payload"], parsed["crc8_valid"])

        assert not buf.is_complete("KK6BZB", tx_id)

    def _reassemble_and_decode(self, buf, tx_id, end_frame_str):
        """Helper: reassemble chunks, decompress if needed, return raw bytes."""
        b64 = buf.reassemble("KK6BZB", tx_id)
        assert b64 is not None
        decoded = base64.b64decode(b64)
        end_parsed = parse_frame(end_frame_str)
        if end_parsed.get("compressed"):
            return decompress_bytes(decoded), end_parsed
        return decoded, end_parsed

    def test_reassemble_matches_original(self):
        buf = TransactionBuffer()
        tx_id, frames, end = encode_transaction(SAMPLE_TX)

        for frame_str in frames:
            parsed = parse_frame(frame_str)
            buf.add_chunk("KK6BZB", tx_id, parsed["seq"], parsed["total"],
                          parsed["payload"], parsed["crc8_valid"])

        raw_bytes, _ = self._reassemble_and_decode(buf, tx_id, end)
        assert raw_bytes.hex() == SAMPLE_TX.lower()

    def test_crc32_matches(self):
        buf = TransactionBuffer()
        tx_id, frames, end = encode_transaction(SAMPLE_TX)

        for frame_str in frames:
            parsed = parse_frame(frame_str)
            buf.add_chunk("KK6BZB", tx_id, parsed["seq"], parsed["total"],
                          parsed["payload"], parsed["crc8_valid"])

        raw_bytes, end_parsed = self._reassemble_and_decode(buf, tx_id, end)
        assert crc32(raw_bytes) == end_parsed["crc32"]

    def test_out_of_order_chunks(self):
        """Chunks arriving out of order should still reassemble correctly."""
        buf = TransactionBuffer()
        tx_id, frames, end = encode_transaction(SAMPLE_TX)

        # Add chunks in reverse order
        for frame_str in reversed(frames):
            parsed = parse_frame(frame_str)
            buf.add_chunk("KK6BZB", tx_id, parsed["seq"], parsed["total"],
                          parsed["payload"], parsed["crc8_valid"])

        assert buf.is_complete("KK6BZB", tx_id)
        raw_bytes, _ = self._reassemble_and_decode(buf, tx_id, end)
        assert raw_bytes.hex() == SAMPLE_TX.lower()

    def test_crc8_failure_blocks_reassembly(self):
        """If any chunk has CRC8 failure, reassemble returns None."""
        buf = TransactionBuffer()
        tx_id, frames, end = encode_transaction(SAMPLE_TX)

        for i, frame_str in enumerate(frames):
            parsed = parse_frame(frame_str)
            # Mark the second chunk as CRC-failed
            crc_valid = (i != 1)
            buf.add_chunk("KK6BZB", tx_id, parsed["seq"], parsed["total"],
                          parsed["payload"], crc_valid)

        assert buf.is_complete("KK6BZB", tx_id)
        assert buf.reassemble("KK6BZB", tx_id) is None

    def test_separate_sessions(self):
        """Different tx_ids don't interfere with each other."""
        buf = TransactionBuffer()

        tx_id1, frames1, _ = encode_transaction(SAMPLE_TX)
        tx_id2, frames2, _ = encode_transaction(SAMPLE_TX)

        # Add only first chunk of each
        p1 = parse_frame(frames1[0])
        p2 = parse_frame(frames2[0])
        buf.add_chunk("KK6BZB", tx_id1, p1["seq"], p1["total"], p1["payload"], True)
        buf.add_chunk("KK6BZB", tx_id2, p2["seq"], p2["total"], p2["payload"], True)

        # Neither should be complete
        assert not buf.is_complete("KK6BZB", tx_id1)
        assert not buf.is_complete("KK6BZB", tx_id2)

    def test_different_senders(self):
        """Same tx_id from different callsigns are separate sessions."""
        buf = TransactionBuffer()
        tx_id, frames, _ = encode_transaction(SAMPLE_TX)

        parsed = parse_frame(frames[0])
        buf.add_chunk("KK6BZB", tx_id, parsed["seq"], parsed["total"], parsed["payload"], True)
        buf.add_chunk("W1AW", tx_id, parsed["seq"], parsed["total"], parsed["payload"], True)

        # Each only has 1 chunk, neither complete
        assert not buf.is_complete("KK6BZB", tx_id)
        assert not buf.is_complete("W1AW", tx_id)

    def test_remove(self):
        buf = TransactionBuffer()
        tx_id, frames, _ = encode_transaction(SAMPLE_TX)

        for frame_str in frames:
            parsed = parse_frame(frame_str)
            buf.add_chunk("KK6BZB", tx_id, parsed["seq"], parsed["total"],
                          parsed["payload"], True)

        assert buf.is_complete("KK6BZB", tx_id)
        buf.remove("KK6BZB", tx_id)
        assert not buf.is_complete("KK6BZB", tx_id)
