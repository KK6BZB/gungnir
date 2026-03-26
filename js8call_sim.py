#!/usr/bin/env python3
"""JS8Call UDP API Simulator — stands in for JS8Call during testing.

Simulates what JS8Call does on the wire:
1. Sender/gateway connect by sending TX.SEND_MESSAGE to this port
2. Simulator extracts the @CALLSIGN directed text
3. Delivers it as RX.DIRECTED to the OTHER connected client

This is exactly what real JS8Call does: encode -> RF -> decode -> UDP emit.
The simulator just skips the RF part.

Usage:
    python js8call_sim.py                    # Default port 2242
    python js8call_sim.py --delay 1.0        # 1s simulated propagation
"""

import argparse
import socket
import json
import time
import re
import threading
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="JS8Call UDP API Simulator")
    parser.add_argument("--port", type=int, default=2242, help="UDP listen port (default 2242)")
    parser.add_argument("--delay", type=float, default=0.2, help="Simulated propagation delay in seconds")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", args.port))

    # Track all connected clients: addr -> callsign (learned from @TO in their messages)
    # When client A sends "@GATEWAY_CALL text", we deliver to the client that IS gateway.
    # We learn who is who from the messages they send.
    clients = {}  # (ip, port) -> {"callsign": str or None}

    print()
    print(f"  JS8Call Simulator v1.0")
    print(f"  ======================")
    print(f"  Listening:  127.0.0.1:{args.port}")
    print(f"  Delay:      {args.delay}s per message")
    print()
    print(f"  Simulates JS8Call's UDP API. Start Gungnir gateway and sender")
    print(f"  pointing at port {args.port} — messages route between them.")
    print()

    while True:
        try:
            data, addr = sock.recvfrom(65535)
        except Exception:
            continue

        try:
            msg = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            continue

        msg_type = msg.get("type", "")
        ts = datetime.now().strftime("%H:%M:%S")

        # Register every client we hear from
        if addr not in clients:
            clients[addr] = {"callsign": None}
            print(f"  [{ts}] New client registered: {addr}")

        # STATION.GET_CALLSIGN — health check
        if msg_type == "STATION.GET_CALLSIGN":
            resp = {"type": "STATION.CALLSIGN", "value": "SIM"}
            sock.sendto(json.dumps(resp).encode(), addr)
            print(f"  [{ts}] Callsign query from {addr} -- responded SIM")
            continue

        # TX.SEND_MESSAGE — the main event
        if msg_type == "TX.SEND_MESSAGE":
            to_call = msg.get("value", "").upper()
            text = msg.get("params", {}).get("TEXT", "")

            # Strip @CALLSIGN prefix
            stripped = re.sub(r'^@\S+\s+', '', text)

            # Determine sender's callsign from the Gungnir frame or context
            # Gateway sends ACK/NAK with its callsign in the --callsign arg
            # Sender doesn't identify itself in frames, but we can track by address

            print(f"  [{ts}] TX {addr[1]} -> @{to_call}: {stripped[:65]}{'...' if len(stripped) > 65 else ''}")

            # Deliver to all OTHER clients as RX.DIRECTED
            def deliver(sender_addr=addr, dest_call=to_call, payload=stripped):
                time.sleep(args.delay)

                rx_msg = {
                    "type": "RX.DIRECTED",
                    "value": {
                        "FROM": f"STA-{sender_addr[1]}",
                        "TO": dest_call,
                        "TEXT": payload,
                    }
                }

                delivered = False
                for client_addr in list(clients.keys()):
                    if client_addr != sender_addr:
                        # Set FROM to sender's known callsign or fallback
                        from_call = clients.get(sender_addr, {}).get("callsign") or f"STA-{sender_addr[1]}"
                        rx_msg["value"]["FROM"] = from_call

                        sock.sendto(json.dumps(rx_msg).encode(), client_addr)
                        dts = datetime.now().strftime("%H:%M:%S")
                        print(f"  [{dts}] RX -> {client_addr[1]} ({dest_call}): {payload[:50]}...")
                        delivered = True

                        # Learn: if this client receives messages for dest_call,
                        # then dest_call is their callsign
                        clients[client_addr]["callsign"] = dest_call

                if not delivered:
                    dts = datetime.now().strftime("%H:%M:%S")
                    print(f"  [{dts}] ** No other client to deliver to — start the other side **")

            threading.Thread(target=deliver, daemon=True).start()
            continue

        print(f"  [{ts}] Unknown msg type: {msg_type}")


if __name__ == "__main__":
    main()
