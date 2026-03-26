#!/usr/bin/env python3
"""Gungnir — Bitcoin Transaction Relay Over HF Radio via JS8Call.

Valhalla Systems — KK6BZB

Usage:
    python gungnir.py send --tx <raw_hex> --to <gateway_callsign> [--testnet] [--port 2242]
    python gungnir.py send --tx-file signed_tx.txt --to <gateway_callsign> [--testnet]
    python gungnir.py gateway --callsign <my_callsign> [--testnet] [--port 2242]
    python gungnir.py gateway --callsign <my_call> --node http://localhost:8332 --rpc-user user --rpc-pass pass
"""

import argparse
import logging
import sys

from config import VERSION, JS8CALL_HOST, JS8CALL_PORT, RIG_PROFILES, DEFAULT_RIG
from js8call_api import JS8CallAPI, LoopbackAPI
from sender import send_transaction
from gateway import run_gateway
from relay import run_relay


def main():
    parser = argparse.ArgumentParser(
        prog="gungnir",
        description=f"Gungnir v{VERSION} — Bitcoin Transaction Relay Over HF Radio via JS8Call",
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # --- Sender mode ---
    send_parser = subparsers.add_parser("send", help="Transmit a signed Bitcoin transaction")
    tx_group = send_parser.add_mutually_exclusive_group(required=True)
    tx_group.add_argument("--tx", type=str, help="Raw signed transaction hex string")
    tx_group.add_argument("--tx-file", type=str, help="Path to file containing raw tx hex")
    send_parser.add_argument("--to", required=True, type=str, help="Gateway callsign")
    send_parser.add_argument("--testnet", action="store_true", default=True, help="Use testnet (default)")
    send_parser.add_argument("--mainnet", action="store_true", help="Use mainnet")
    send_parser.add_argument("--host", type=str, default=JS8CALL_HOST, help="JS8Call API host")
    send_parser.add_argument("--port", type=int, default=JS8CALL_PORT, help="JS8Call API port")
    rig_choices = list(RIG_PROFILES.keys())
    rig_help = ", ".join(f"{k} ({v['name']})" for k, v in RIG_PROFILES.items())
    send_parser.add_argument("--rig", type=str, default=DEFAULT_RIG, choices=rig_choices,
                             help=f"Rig thermal profile: {rig_help}")
    send_parser.add_argument("--loopback", action="store_true",
                             help="Loopback mode — send directly via UDP to gateway (no JS8Call)")
    send_parser.add_argument("--loopback-port", type=int, default=0,
                             help="Sender bind port for loopback mode (0 = auto)")
    send_parser.add_argument("--gateway-port", type=int, default=None,
                             help="Gateway listen port for loopback mode")
    send_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    # --- Gateway mode ---
    gw_parser = subparsers.add_parser("gateway", help="Listen for and relay transactions")
    gw_parser.add_argument("--callsign", required=True, type=str, help="This station's callsign")
    gw_parser.add_argument("--testnet", action="store_true", default=True, help="Use testnet (default)")
    gw_parser.add_argument("--mainnet", action="store_true", help="Use mainnet")
    gw_parser.add_argument("--node", type=str, help="Bitcoin Core RPC URL")
    gw_parser.add_argument("--rpc-user", type=str, help="Bitcoin Core RPC username")
    gw_parser.add_argument("--rpc-pass", type=str, help="Bitcoin Core RPC password")
    gw_parser.add_argument("--host", type=str, default=JS8CALL_HOST, help="JS8Call API host")
    gw_parser.add_argument("--port", type=int, default=JS8CALL_PORT, help="JS8Call API port")
    gw_parser.add_argument("--no-broadcast", action="store_true",
                            help="Skip Bitcoin broadcast (test mode — reassemble and ACK only)")
    gw_parser.add_argument("--loopback", action="store_true",
                            help="Loopback mode — listen on direct UDP (no JS8Call)")
    gw_parser.add_argument("--loopback-port", type=int, default=0,
                            help="Gateway bind port for loopback mode (0 = auto)")
    gw_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    # --- Relay mode ---
    relay_parser = subparsers.add_parser("relay", help="Store-and-forward relay (no internet needed)")
    relay_parser.add_argument("--callsign", required=True, type=str, help="This relay station's callsign")
    relay_parser.add_argument("--to", required=True, type=str, help="Next hop callsign (relay or gateway)")
    relay_parser.add_argument("--host", type=str, default=JS8CALL_HOST, help="JS8Call API host")
    relay_parser.add_argument("--port", type=int, default=JS8CALL_PORT, help="JS8Call API port")
    relay_parser.add_argument("--rig", type=str, default=DEFAULT_RIG, choices=rig_choices,
                              help=f"Rig thermal profile: {rig_help}")
    relay_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    testnet = not args.mainnet

    if args.mode == "send":
        # Load transaction
        if args.tx_file:
            try:
                with open(args.tx_file, "r") as f:
                    raw_tx = f.read().strip()
            except FileNotFoundError:
                print(f"Error: file not found: {args.tx_file}")
                sys.exit(1)
        else:
            raw_tx = args.tx

        if args.loopback:
            if not args.gateway_port:
                print("Error: --gateway-port is required in loopback mode")
                print("  Start the gateway first to see its port, then pass it here.")
                sys.exit(1)
            api = LoopbackAPI(
                my_callsign="SENDER",
                bind_port=args.loopback_port,
                peer_port=args.gateway_port,
            )
            rig = "none"  # no thermal delays in loopback
        else:
            api = JS8CallAPI(host=args.host, port=args.port)
            rig = args.rig

        with api as js8:
            result = send_transaction(
                raw_tx_hex=raw_tx,
                gateway_callsign=args.to.upper(),
                js8=js8,
                testnet=testnet,
                rig=rig,
            )
            sys.exit(0 if result["success"] else 1)

    elif args.mode == "gateway":
        if args.loopback:
            api = LoopbackAPI(
                my_callsign=args.callsign.upper(),
                bind_port=args.loopback_port,
            )
            print(f"  Loopback gateway listening on port {api.local_port}")
            print(f"  Start sender with: --loopback --gateway-port {api.local_port}")
            print()
        else:
            api = JS8CallAPI(host=args.host, port=args.port)

        with api as js8:
            try:
                run_gateway(
                    my_callsign=args.callsign.upper(),
                    js8=js8,
                    testnet=testnet,
                    node_url=args.node,
                    rpc_user=args.rpc_user,
                    rpc_pass=args.rpc_pass,
                    no_broadcast=getattr(args, 'no_broadcast', False),
                )
            except KeyboardInterrupt:
                print("\n  Gateway stopped. 73!")
                sys.exit(0)

    elif args.mode == "relay":
        with JS8CallAPI(host=args.host, port=args.port) as js8:
            try:
                run_relay(
                    my_callsign=args.callsign.upper(),
                    next_hop=args.to.upper(),
                    js8=js8,
                    rig=args.rig,
                )
            except KeyboardInterrupt:
                print("\n  Relay stopped. 73!")
                sys.exit(0)


if __name__ == "__main__":
    main()
