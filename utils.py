"""Shared utilities — validation, encoding helpers."""

import re
import base64


def is_valid_hex(s: str) -> bool:
    """Check if string is valid hexadecimal."""
    return bool(re.fullmatch(r'[0-9a-fA-F]+', s))


def is_valid_raw_tx(hex_str: str) -> bool:
    """Basic structural validation of a raw Bitcoin transaction hex string.

    Checks:
    - Valid hex
    - Even length (full bytes)
    - Reasonable length (at least 60 bytes for minimal tx)
    - Starts with a valid version (01000000 or 02000000)
    """
    if not is_valid_hex(hex_str):
        return False
    if len(hex_str) % 2 != 0:
        return False
    if len(hex_str) < 120:  # 60 bytes minimum
        return False
    # Version bytes: 01000000 or 02000000
    version = hex_str[:8]
    if version not in ("01000000", "02000000"):
        return False
    return True


def hex_to_base64(hex_str: str) -> str:
    """Convert hex string to base64 string."""
    raw_bytes = bytes.fromhex(hex_str)
    return base64.b64encode(raw_bytes).decode("ascii")


def base64_to_hex(b64_str: str) -> str:
    """Convert base64 string back to hex string."""
    raw_bytes = base64.b64decode(b64_str)
    return raw_bytes.hex()


def callsign_valid(callsign: str) -> bool:
    """Basic amateur radio callsign format check."""
    return bool(re.fullmatch(r'[A-Z0-9]{3,10}', callsign.upper()))
