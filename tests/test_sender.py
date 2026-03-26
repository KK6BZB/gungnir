"""Tests for Gungnir Sender — mock JS8Call API, verify frame output."""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framing import parse_frame, encode_ack_frame, encode_nak_frame
from sender import send_transaction
from config import PROTOCOL_ID
import config


@pytest.fixture(autouse=True)
def fast_timeout():
    """All sender tests use a 1-second ACK timeout."""
    original = config.ACK_TIMEOUT_SECONDS
    config.ACK_TIMEOUT_SECONDS = 1
    yield
    config.ACK_TIMEOUT_SECONDS = original


class MockJS8CallAPI:
    """Mock JS8Call API that captures sent messages and can inject responses."""

    def __init__(self, responses=None):
        self.sent_messages = []
        self.responses = responses or []
        self._response_idx = 0

    def send_message(self, to_callsign, text):
        self.sent_messages.append({"to": to_callsign, "text": text})

    def listen(self, timeout=None):
        if self._response_idx < len(self.responses):
            resp = self.responses[self._response_idx]
            self._response_idx += 1
            return resp
        return None

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# Sample valid tx hex (version 2 segwit)
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


class TestSenderFrameOutput:
    def test_sends_correct_number_of_frames(self):
        mock = MockJS8CallAPI()
        result = send_transaction(SAMPLE_TX, "KE7ABC", mock, testnet=True, rig="none")

        # Should have sent N data frames + 1 END frame
        sent = mock.sent_messages
        assert len(sent) >= 2  # at least 1 data frame + 1 END

        # Last frame should be an END frame
        last_text = sent[-1]["text"]
        parsed = parse_frame(last_text)
        assert parsed is not None
        assert parsed["type"] == "end"

        # All prior frames should be data frames
        for msg in sent[:-1]:
            parsed = parse_frame(msg["text"])
            assert parsed is not None
            assert parsed["type"] == "data"
            assert parsed["crc8_valid"] is True

    def test_all_frames_addressed_to_gateway(self):
        mock = MockJS8CallAPI()
        send_transaction(SAMPLE_TX, "KE7ABC", mock, testnet=True, rig="none")

        for msg in mock.sent_messages:
            assert msg["to"] == "KE7ABC"

    def test_invalid_tx_returns_error(self):
        mock = MockJS8CallAPI()
        result = send_transaction("not_valid_hex", "KE7ABC", mock, testnet=True)
        assert result["success"] is False
        assert "Invalid" in result["error"]
        assert len(mock.sent_messages) == 0

    def test_timeout_no_ack(self):
        """No ACK received — should timeout gracefully."""
        mock = MockJS8CallAPI()  # no responses = timeout
        result = send_transaction(SAMPLE_TX, "KE7ABC", mock, testnet=True, rig="none")
        assert result["success"] is False

    def test_sender_consistent_tx_id(self):
        """All frames from one send should share the same tx_id."""
        mock = MockJS8CallAPI()
        send_transaction(SAMPLE_TX, "KE7ABC", mock, testnet=True, rig="none")

        tx_ids = set()
        for msg in mock.sent_messages:
            parsed = parse_frame(msg["text"])
            if parsed:
                tx_ids.add(parsed["tx_id"])

        assert len(tx_ids) == 1  # all frames share one session ID
