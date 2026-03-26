# Gungnir

**Bitcoin Transaction Relay Over HF Amateur Radio via JS8Call**

*Odin's spear never misses its target. Your transaction always reaches the network.*

---

## What Is Gungnir?

Gungnir relays signed Bitcoin transactions over amateur radio using JS8Call as the transport layer. It enables Bitcoin usage without internet access — for disaster scenarios, censorship resistance, or anywhere internet infrastructure is unavailable.

You sign a transaction offline on your laptop. Gungnir encodes it, chunks it into radio-sized frames, and transmits it over HF radio via JS8Call. A volunteer gateway operator receives the transmission, reassembles the transaction, and broadcasts it to the Bitcoin network. Your Bitcoin moves without ever touching the internet on your end.

```
┌─────────────────────┐         HF Radio (40m)        ┌─────────────────────┐
│   SENDER (off-grid) │ ──── JS8Call ──── air ──── ──> │  GATEWAY (internet) │
│                     │                                │                     │
│  Sparrow/Electrum   │                                │  Reassemble tx      │
│  Sign offline       │                                │  Verify checksum    │
│  Gungnir encodes    │                                │  Broadcast to       │
│  JS8Call transmits  │                                │  Bitcoin network    │
│                     │  <──── ACK (TXID) ──────────── │  Send confirmation  │
└─────────────────────┘                                └─────────────────────┘
```

## Origin Story

This project didn't start in 2026. In 2016, the author worked with another ham operator to relay Bitcoin transactions over VHF radio using FLDIGI and Armory wallets — three years before NVK's widely-publicized JS8Call Bitcoin transmission made international crypto news in 2019.

That 2016 experiment was manual, clunky, and short-range (VHF is line-of-sight). Gungnir automates the entire process and runs on HF, which means ionospheric propagation — continental range, even on low power, even under terrible band conditions.

The technology on both sides has improved dramatically since 2016. JS8Call's FT8-derived modulation decodes signals at -24dB SNR — buried in noise you can't even hear. Modern wallets like Sparrow handle offline signing in a single step. Gungnir connects these two worlds with purpose-built tooling that didn't exist until now.

## How It Works

### The Sender (Off-Grid Operator)

1. Sign a Bitcoin transaction offline using Sparrow, Electrum, or any wallet that exports raw transaction hex
2. Paste the raw hex into Gungnir
3. Gungnir base64-encodes the transaction, splits it into radio-sized chunks, adds per-chunk CRC8 checksums and a full CRC32 integrity check
4. Each chunk is transmitted as a directed JS8Call message to a known gateway callsign
5. Wait for ACK confirmation from the gateway

### The Gateway (Volunteer Relay Operator)

1. Runs Gungnir in gateway mode alongside JS8Call, listening for incoming Gungnir-framed messages
2. Reassembles chunks in order, verifies per-chunk CRC8 and full CRC32
3. Broadcasts the validated transaction to the Bitcoin network (via mempool.space API or a local Bitcoin node)
4. Sends an ACK back to the sender over JS8Call with the first 8 characters of the TXID

### Transaction Size and Airtime

A simple 1-input, 2-output SegWit transaction is approximately 110 vbytes, which encodes to roughly 147 characters of base64. At JS8Call Normal speed, this takes about 45-60 seconds of airtime. Turbo mode reduces this to approximately 20 seconds.

More complex transactions with multiple inputs will take longer. Gungnir warns if a transaction exceeds a reasonable airtime threshold.

## Prerequisites

- Python 3.9+
- JS8Call (original v2.2.0 confirmed working; JS8Call-improved has a known issue with UDP API binding on some builds)
- Amateur radio license — General class or higher for HF privileges
- HF radio and antenna (for on-air use; not needed for localhost testing)
- A wallet that can sign transactions offline and export raw hex (Sparrow, Electrum, Bitcoin Core)

## Quick Start

### Sender

```bash
python gungnir.py send --tx <raw_hex_transaction> --to <gateway_callsign> --testnet
```

### Gateway

```bash
python gungnir.py gateway --callsign <your_callsign> --testnet
```

### Localhost Testing (No Radio Needed)

```bash
# Terminal 1 — start gateway in loopback mode
python gungnir.py gateway --callsign TEST-GW --testnet --loopback

# Terminal 2 — send a test transaction
python gungnir.py send --tx <any_hex_string> --to TEST-GW --testnet --loopback
```

## JS8Call Configuration

1. Open JS8Call
2. Go to Configurations → Reporting
3. Enable "UDP Server API"
4. Set UDP Server Port to 2242
5. Enable "Accept UDP Requests"
6. Click OK

Note: Some builds require a full restart of JS8Call after enabling the UDP API. If Gungnir can't connect, close JS8Call completely and reopen it.

### JS8Call Version Notes

- **JS8Call original (v2.2.0):** UDP API confirmed working. Recommended for current use.
- **JS8Call-improved (v2.4.0+):** Has a known issue where the UDP API server doesn't bind on some Windows builds despite the setting being enabled. TCP API may work as an alternative. This is a config/build issue, not a fundamental incompatibility — Gungnir will support JS8Call-improved as the issue is resolved.

## Gateway Incentives

Gateway operators are volunteers, just like APRS iGate operators, Winlink RMS node operators, and Bitcoin full node runners. No payment is involved — this is by design, not oversight.

Paying gateway operators in satoshis would violate FCC Part 97's prohibition on pecuniary interest and would destroy the project's legitimacy with the ham radio community.

The incentive model is reputation and community service. Ham radio has been running on volunteerism and community pride for over a century. Bitcoin full nodes run on the same principle — people do it because censorship resistance matters and the network is stronger when more people participate.

## Security Considerations

### What Gungnir Is and Is Not

**Gungnir is a censorship resistance and disaster resilience tool.** It is designed for scenarios where internet access is unavailable — natural disasters, infrastructure failure, government censorship. It enables Bitcoin transactions to reach the network when no other path exists.

**Gungnir is not a privacy tool.** If you have internet access and want private Bitcoin transactions, use Tor, a VPN, or your own node. Gungnir should be chosen over nothing, not over better options.

### Cryptographic Security

Gungnir does not modify Bitcoin's security model in any way. Transactions are signed with the same ECDSA/Schnorr cryptography regardless of transport layer. JS8Call is a dumb pipe carrying bytes — the cryptographic protection is in the transaction itself, not the delivery method.

A signed Bitcoin transaction cannot be modified, reversed, or stolen by intercepting it in transit. If someone captures your transmission and rebroadcasts it, nothing happens — Bitcoin nodes reject duplicate transactions.

### Privacy Tradeoffs

**Callsign = real identity.** FCC Part 97 requires station identification on amateur radio. Every JS8Call transmission includes your callsign, which is linked to your legal name and address in the public FCC ULS database. Anyone monitoring the frequency can see that your callsign sent a Bitcoin transaction and look up who you are.

**Transmissions are plaintext.** FCC prohibits encryption on amateur radio. Your transaction data is visible to anyone monitoring the frequency. However, Bitcoin transactions are designed to be public — the entire network sees them once broadcast. Interception during radio transit reveals nothing that won't be public on the blockchain within minutes.

**Direction finding.** HF transmissions can be direction-found with specialized equipment, giving an approximate geographic location of the sender. This is less precise than IP geolocation but is a consideration.

**Gateway operators see your data.** The gateway operator sees your callsign, your raw transaction (amounts, addresses), and the time. This is the same trust model as connecting to someone else's Electrum server or using a public mempool API — you're trusting infrastructure operators. The difference is the callsign makes you non-anonymous to the operator.

### Mitigations

- **Multi-gateway broadcast (planned):** Send to multiple gateways simultaneously so no single operator is exclusively relied upon
- **Gateway reputation system (planned):** Prefer established gateways with long track records over unknown callsigns
- **Transaction construction discipline:** Use intermediary addresses rather than sending directly to final destinations; don't move your entire stack through Gungnir
- **CoinJoin/PayJoin before sending:** Obscure the on-chain trail so addresses in the transaction are less linkable to you even if the callsign identifies the sender

### Malicious Gateway Operators

A malicious actor could theoretically run a gateway to correlate callsigns with Bitcoin transactions. In practice this attack is limited: it requires an amateur radio license and station, HF direction finding gives rough areas not street addresses, and amounts moving through Gungnir would typically be small emergency transactions.

Ham radio is a small, self-policing community where callsigns are permanent reputations. A gateway operator who misused their position would be identified and blacklisted. This is a stronger social enforcement mechanism than exists for anonymous internet infrastructure.

### Quantum Computing

Quantum computing concerns apply to Bitcoin's underlying elliptic curve cryptography, not to Gungnir's transport layer. If quantum computers capable of breaking ECDSA existed, the threat would be to the entire Bitcoin network — not specifically to the handful of transactions relayed over amateur radio. An attacker with that capability would target the blockchain directly, not point an antenna at 40 meters hoping to intercept one transaction.

## FCC Regulatory Considerations

### 97.113(a)(3) — Pecuniary Interest

FCC Part 97.113(a)(3) prohibits amateur radio transmissions "in which the station licensee or control operator has a pecuniary interest." Sending a Bitcoin transaction arguably involves pecuniary interest, as it is literally moving money.

This rule has never been tested or ruled on by the FCC in the context of Bitcoin or cryptocurrency transactions. The counterargument is that the operator is transmitting a pre-signed data blob — not conducting commerce or negotiating a deal over the air. The pecuniary interest rule was written to prevent commercial radio operations, not to prohibit transmitting encoded data that happens to contain financial instructions.

**Precedent:** In February 2019, Rodolfo Novak (NVK) publicly transmitted a Bitcoin brain wallet over JS8Call on the 40-meter band from Toronto to Michigan. The transmission was widely publicized, discussed by Nick Szabo, and covered by international media. The FCC took no action.

Gateway operators arguably have even less exposure, as they are relaying data on behalf of another station — similar to an APRS digipeater or Winlink relay.

### 97.113(a)(4) — Codes and Ciphers

Bitcoin transactions are encoded (base64, hex) but not encrypted. The data is publicly verifiable on the blockchain. Every digital mode — FT8, PSK31, JS8 itself — uses encoding. This provision is almost certainly not an issue.

### 97.119 — Station Identification

JS8Call handles station identification automatically per FCC requirements.

### 97.403 — Safety of Life

In immediate safety-of-life situations, FCC Part 97.403 permits the use of any means of communication regardless of normal rules. In a true disaster or emergency scenario, regulatory compliance is secondary to survival.

### This Is Not Legal Advice

This section documents the regulatory landscape as understood by the project maintainers. We are not lawyers. Users are responsible for compliance with their jurisdiction's laws and regulations. If you intend to use Gungnir commercially or in a context where regulatory compliance is critical, consult an attorney familiar with FCC Part 97 and financial regulations.

### How Gungnir Differs from Samourai Wallet

Gungnir is a transport layer, not a financial service. It never has custody of funds, does not modify transactions, does not mix or pool anything, does not obscure the origin or destination of funds, and has no business model based on facilitating financial activity. Gateway operators are ham radio volunteers, not financial service providers.

Samourai Wallet's founders were charged with operating an unlicensed money transmitting business and conspiracy to commit money laundering based on features specifically designed to obscure transaction origins. Gungnir has no such features and serves a fundamentally different purpose.

## Technical Notes

### Supported Wallets

Any wallet that can sign transactions offline and export raw transaction hex works with Gungnir. The wallet is the brain — Gungnir is just the delivery mechanism. Tested with:

- **Sparrow Wallet** (recommended — clear "Copy Transaction Hex" workflow)
- **Electrum**
- **Bitcoin Core**

### Why Not Encrypt?

FCC Part 97 prohibits encryption on amateur radio frequencies. Gungnir transmissions are plaintext by design and by legal requirement. This is a feature, not a bug — it means the project operates within regulatory boundaries and the ham community can embrace it without legal concerns.

Bitcoin transactions don't need transport-layer encryption because they are cryptographically self-securing. The signature protects the transaction, not the transport.

### Network Architecture

Gungnir's gateway model is architecturally similar to existing ham radio infrastructure: APRS iGates relay APRS packets to the internet, Winlink RMS nodes relay email, and Gungnir gateways relay Bitcoin transactions. All are volunteer-operated, all bridge radio and internet, and all serve the principle that amateur radio infrastructure should be resilient and community-driven.

## Roadmap

### Completed (MVP)
- CLI sender and gateway modes
- Message framing protocol with per-chunk CRC8 and full CRC32
- JS8Call UDP API integration
- Loopback testing mode
- Testnet and mainnet support

### Phase 2 — Usability
- Desktop GUI
- Gateway discovery beacon (CQ GUNGNIR)
- ARQ retransmission for corrupted chunks
- Multi-gateway redundancy
- Improved error handling and user feedback

### Phase 3 — Network Scale
- Gateway honor roll and uptime leaderboard
- Comprehensive documentation for gateway setup
- Community outreach to ham radio and Bitcoin communities

### Phase 4 — Advanced
- PSBT support for multisig workflows
- Lightning invoice relay
- Mobile support (dependent on JS8Call Android port)
- Transaction compression

## License

MIT

## Credits

Built by Brandon Todd, KK6BZB
Valhalla Systems — Tucson, AZ
2026

Gungnir would not exist without:
- **JS8Call** by Jordan Sherer, KN4CRD — the weak-signal transport layer that makes this possible
- **JS8Call-improved** community — continuing development of the JS8Call project
- **Bitcoin** — the reason any of this matters

---

*"Bitcoin and amateur radio share the same DNA: decentralized, permissionless, censorship-resistant, run by volunteers who believe the infrastructure matters. Gungnir doesn't force these two worlds together — they were always building toward the same thing."*
