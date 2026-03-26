"""Tests for Gungnir Relay — buffer and forward behavior."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framing import encode_transaction, parse_frame
from relay import RelayBuffer


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


class TestRelayBuffer:
    def test_buffer_and_retrieve(self):
        """Relay buffers all frames and returns them in order."""
        buf = RelayBuffer()
        tx_id, data_frames, end_frame = encode_transaction(SAMPLE_TX)

        for frame in data_frames:
            buf.add_frame("KK6BZB", tx_id, frame)
        buf.add_frame("KK6BZB", tx_id, end_frame)

        stored = buf.get_frames("KK6BZB", tx_id)
        assert len(stored) == len(data_frames) + 1  # data + END

        # Verify frames are retrievable and parseable
        for frame_str in stored:
            parsed = parse_frame(frame_str)
            assert parsed is not None

    def test_frames_preserve_order(self):
        """Frames come back in the order they were added."""
        buf = RelayBuffer()
        tx_id, data_frames, end_frame = encode_transaction(SAMPLE_TX)

        all_frames = data_frames + [end_frame]
        for frame in all_frames:
            buf.add_frame("KK6BZB", tx_id, frame)

        stored = buf.get_frames("KK6BZB", tx_id)
        assert stored == all_frames

    def test_frames_unchanged(self):
        """Relay must not modify frame content — pass-through only."""
        buf = RelayBuffer()
        tx_id, data_frames, end_frame = encode_transaction(SAMPLE_TX)

        for frame in data_frames:
            buf.add_frame("KK6BZB", tx_id, frame)
        buf.add_frame("KK6BZB", tx_id, end_frame)

        stored = buf.get_frames("KK6BZB", tx_id)
        for original, relayed in zip(data_frames + [end_frame], stored):
            assert original == relayed

    def test_separate_senders(self):
        """Different senders are isolated."""
        buf = RelayBuffer()
        tx_id, frames, end = encode_transaction(SAMPLE_TX)

        buf.add_frame("KK6BZB", tx_id, frames[0])
        buf.add_frame("W1AW", tx_id, frames[0])

        assert len(buf.get_frames("KK6BZB", tx_id)) == 1
        assert len(buf.get_frames("W1AW", tx_id)) == 1

    def test_remove(self):
        buf = RelayBuffer()
        tx_id, frames, end = encode_transaction(SAMPLE_TX)

        buf.add_frame("KK6BZB", tx_id, frames[0])
        assert len(buf.get_frames("KK6BZB", tx_id)) == 1

        buf.remove("KK6BZB", tx_id)
        assert len(buf.get_frames("KK6BZB", tx_id)) == 0

    def test_empty_buffer(self):
        buf = RelayBuffer()
        assert buf.get_frames("NOBODY", "0000") == []
