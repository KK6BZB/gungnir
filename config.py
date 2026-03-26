"""Gungnir configuration constants."""

VERSION = "0.1.0"
PROTOCOL_ID = "GUNGNIR"

# JS8Call UDP API
JS8CALL_HOST = "127.0.0.1"
JS8CALL_PORT = 2242

# Framing
TX_ID_LENGTH = 4            # hex chars
MAX_PAYLOAD_PER_FRAME = 50  # chars of base64 per chunk
FRAME_TIMEOUT_SECONDS = 600  # 10 min timeout for incomplete sessions
ACK_TIMEOUT_SECONDS = 300    # 5 min wait for ACK after sending
COMPRESS = True              # zlib compress before base64 (saves ~20-40% airtime)

# JS8Call speed modes — approximate TX time per frame (seconds)
JS8_SPEEDS = {
    "slow":   30,   # JS8Call Slow — best sensitivity, -28 dB SNR
    "normal": 15,   # JS8Call Normal — standard, -24 dB SNR
    "fast":   10,   # JS8Call Fast — decent conditions, -20 dB SNR
    "turbo":   6,   # JS8Call Turbo — strong signal only, -18 dB SNR
}

# --- Rig Profiles ---
# Each profile defines thermal-safe TX behavior for a specific radio.
# Digital modes are 100% duty cycle during TX — much harder on finals
# than SSB voice (~30% duty). These profiles keep your PA alive.
#
#   cooldown:        seconds of rest between each frame TX
#   max_continuous:  max frames before a mandatory long break
#   long_break:      seconds to rest after max_continuous frames
#   max_power_note:  suggested power level for digital modes

RIG_PROFILES = {
    "g90": {
        "name": "Xiegu G90",
        "cooldown": 10,
        "max_continuous": 3,
        "long_break": 30,
        "max_power_note": "15W or below — thermal cutoff at 20W sustained",
    },
    "ft857": {
        "name": "Yaesu FT-857/D",
        "cooldown": 5,
        "max_continuous": 6,
        "long_break": 15,
        "max_power_note": "50W comfortable — 100W needs external fan",
    },
    "qrp": {
        "name": "QRP / Portable (5W)",
        "cooldown": 5,
        "max_continuous": 8,
        "long_break": 10,
        "max_power_note": "5W — low thermal stress, short breaks are fine",
    },
    "base": {
        "name": "Base Station (IC-7300, TS-890, etc.)",
        "cooldown": 3,
        "max_continuous": 10,
        "long_break": 10,
        "max_power_note": "50-75W — built for extended digital operation",
    },
    "none": {
        "name": "No thermal management",
        "cooldown": 0,
        "max_continuous": 999,
        "long_break": 0,
        "max_power_note": "Use at your own risk",
    },
}

DEFAULT_RIG = "g90"  # conservative default — protect the gear

# Active rig profile (set by CLI --rig flag, defaults to DEFAULT_RIG)
TX_COOLDOWN_SECONDS = RIG_PROFILES[DEFAULT_RIG]["cooldown"]
TX_MAX_CONTINUOUS = RIG_PROFILES[DEFAULT_RIG]["max_continuous"]
TX_LONG_BREAK = RIG_PROFILES[DEFAULT_RIG]["long_break"]

# Bitcoin broadcast endpoints
MEMPOOL_MAINNET = "https://mempool.space/api/tx"
MEMPOOL_TESTNET = "https://mempool.space/testnet4/api/tx"

# Warnings
MAX_CHUNKS_WARNING = 15  # warn if tx exceeds this many chunks
