"""JS8Call UDP API wrapper.

JS8Call exposes a JSON-over-UDP API on 127.0.0.1:2242 (default).
This module handles sending directed messages and listening for incoming frames.
"""

import socket
import json
import logging

from config import JS8CALL_HOST, JS8CALL_PORT

log = logging.getLogger("gungnir.js8call")


class JS8CallAPI:
    """Interface to JS8Call's UDP API."""

    def __init__(self, host: str = JS8CALL_HOST, port: int = JS8CALL_PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))  # random port for receiving
        self.server = (host, port)
        log.info(f"JS8Call API targeting {host}:{port}")
        # Register with JS8Call so it knows our listen address
        self._ping()

    def _ping(self):
        """Send a registration ping so JS8Call knows our listen address."""
        msg = {"type": "STATION.GET_CALLSIGN", "value": "", "params": {}}
        self.sock.sendto(json.dumps(msg).encode("utf-8"), self.server)

    def send_message(self, to_callsign: str, text: str):
        """Send a directed message to a specific callsign via JS8Call.

        This queues the message in JS8Call's transmit buffer.
        JS8Call handles the actual RF transmission.
        """
        msg = {
            "type": "TX.SEND_MESSAGE",
            "value": to_callsign,
            "params": {"TEXT": f"@{to_callsign} {text}"}
        }
        payload = json.dumps(msg).encode("utf-8")
        self.sock.sendto(payload, self.server)
        log.debug(f"Sent to JS8Call: {to_callsign} ->{text[:60]}...")

    def listen(self, timeout: float | None = None) -> dict | None:
        """Listen for an incoming message from JS8Call.

        Args:
            timeout: Seconds to wait. None = block forever.

        Returns:
            Parsed JSON message dict, or None on timeout.
        """
        self.sock.settimeout(timeout)
        try:
            data, _ = self.sock.recvfrom(65535)
            msg = json.loads(data.decode("utf-8"))
            log.debug(f"Received from JS8Call: {msg.get('type', '?')}")
            return msg
        except socket.timeout:
            return None
        except json.JSONDecodeError as e:
            log.warning(f"Invalid JSON from JS8Call: {e}")
            return None

    def close(self):
        """Close the UDP socket."""
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class LoopbackAPI:
    """Direct UDP transport for localhost testing — bypasses JS8Call entirely.

    Sender and gateway talk directly over UDP, wrapping frames in the same
    RX.DIRECTED JSON format that JS8Call produces. This lets all existing
    parsing code work unchanged.
    """

    def __init__(self, my_callsign: str, bind_port: int = 0, peer_port: int | None = None):
        self.my_callsign = my_callsign.upper()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", bind_port))
        self.local_port = self.sock.getsockname()[1]
        self.peer = ("127.0.0.1", peer_port) if peer_port else None
        self.last_sender = None  # auto-learn peer address from incoming packets
        log.info(f"Loopback API: {my_callsign} on port {self.local_port}"
                 + (f", peer port {peer_port}" if peer_port else ""))

    def send_message(self, to_callsign: str, text: str):
        """Send a frame directly to the peer as a fake RX.DIRECTED message."""
        target = self.peer or self.last_sender
        if not target:
            log.warning("No peer port set and no sender seen yet — cannot send")
            return
        msg = {
            "type": "RX.DIRECTED",
            "value": {
                "FROM": self.my_callsign,
                "TO": to_callsign.upper(),
                "TEXT": text,
            }
        }
        payload = json.dumps(msg).encode("utf-8")
        self.sock.sendto(payload, target)
        log.debug(f"Loopback TX: {self.my_callsign} -> {to_callsign}: {text[:60]}...")

    def listen(self, timeout: float | None = None) -> dict | None:
        """Listen for an incoming loopback message."""
        self.sock.settimeout(timeout)
        try:
            data, addr = self.sock.recvfrom(65535)
            self.last_sender = addr  # remember sender for ACK routing
            msg = json.loads(data.decode("utf-8"))
            log.debug(f"Loopback RX from {addr}: {msg}")
            return msg
        except socket.timeout:
            return None
        except json.JSONDecodeError as e:
            log.warning(f"Invalid JSON on loopback: {e}")
            return None

    def close(self):
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def extract_directed_text(msg: dict) -> tuple[str, str, str] | None:
    """Extract (from_callsign, to_callsign, text) from an RX.DIRECTED message.

    Returns None if the message is not a directed message.
    """
    if msg.get("type") != "RX.DIRECTED":
        return None

    value = msg.get("value", {})
    if isinstance(value, str):
        # Some JS8Call versions put the text directly in value
        return None

    from_call = value.get("FROM", "")
    to_call = value.get("TO", "")
    text = value.get("TEXT", "")

    if not from_call or not text:
        return None

    return from_call, to_call, text
