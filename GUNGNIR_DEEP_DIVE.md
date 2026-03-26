# Gungnir: Bitcoin Over Amateur Radio — The Complete Picture

## For Context

This document covers Gungnir, a working software project built by Brandon Todd (amateur radio callsign KK6BZB) under the name Valhalla Systems, based in Tucson, Arizona. Gungnir relays signed Bitcoin transactions over HF amateur radio using a digital mode called JS8Call. It was built in March 2026 and has been tested end-to-end on localhost through JS8Call's UDP API. The next milestone is a live over-the-air test on the 40-meter band.

---

## The One-Sentence Version

Gungnir lets you send Bitcoin when the internet doesn't exist — using nothing but a laptop, a $200 radio, a piece of wire, and the ionosphere.

---

## Why This Matters

### The Internet Is a Single Point of Failure for Bitcoin

Bitcoin is the most resilient monetary network ever built. It runs on tens of thousands of nodes across every continent. It has never gone down. The protocol itself is essentially unkillable.

But there's a gap. To use Bitcoin — to actually send a transaction — you need internet access. You need to get your signed transaction from your device to at least one node on the network. If you can't reach the internet, your Bitcoin is frozen. Not gone, not stolen — just stuck. You have the keys, you have the funds, but you have no way to move them.

This matters in three scenarios that are not hypothetical:

**Natural disasters.** Hurricane Katrina knocked out cellular and internet infrastructure across the Gulf Coast for weeks. Hurricane Maria left Puerto Rico without communications for months. The 2011 Tohoku earthquake and tsunami destroyed internet infrastructure across northeastern Japan. In all of these events, amateur radio operators provided critical communications when everything else failed. HF radio doesn't need infrastructure — it bounces signals off the ionosphere, which is 60 to 300 miles above the Earth and is not affected by hurricanes, earthquakes, or power outages.

**Government censorship and conflict.** Governments routinely shut down the internet during protests, elections, coups, and military operations. Myanmar's military junta has imposed repeated internet blackouts since the 2021 coup. Iran shut down the internet during the 2022 Mahsa Amini protests. Russia has progressively restricted internet access since the invasion of Ukraine. In these scenarios, people need to move money — to flee, to buy supplies, to support resistance movements — and the government has specifically targeted their ability to do so. There is no kill switch for the ionosphere. You cannot sanction a radio wave. A signed Bitcoin transaction on 40 meters crosses borders without permission, without ISPs, without DNS servers.

**Remote and off-grid locations.** Research stations in Antarctica, maritime vessels in the open ocean, rural communities in developing nations, backcountry expeditions. Anywhere humans exist beyond the reach of broadband but still need to participate in the global economy. A remote weather station with a solar panel, a radio, and a signing key could settle payments autonomously without ever touching the internet.

### The Gap Between "Bitcoin Works" and "I Can Use Bitcoin"

The Bitcoin community talks a lot about censorship resistance, but almost all Bitcoin usage depends on centralized internet infrastructure. Your transaction goes through your ISP, through DNS servers, through routing infrastructure controlled by governments and corporations. Tor helps with privacy but still requires internet connectivity. Satellite downlinks (like Blockstream Satellite) let you receive the blockchain but not transmit transactions.

Gungnir fills the transmit gap. It's the uplink. You sign a transaction with your own keys on your own hardware, and Gungnir gets it to the network through a path that no government, no corporation, and no natural disaster can shut down.

---

## How It Actually Works

### The Core Flow

1. You have a Bitcoin wallet on your laptop — Sparrow, Electrum, whatever. You sign a transaction offline. The wallet gives you a raw transaction as a hexadecimal string. This is a fully valid, cryptographically signed Bitcoin transaction — it just hasn't been broadcast to the network yet.

2. You paste that hex string into Gungnir's command-line tool. Gungnir compresses it with zlib (saving 20-40% of airtime), base64-encodes it, and splits it into chunks of about 50 characters each — sized to fit within JS8Call's message constraints.

3. Each chunk gets wrapped in a protocol frame with a session ID, sequence number, and a CRC8 checksum for error detection. The final frame carries a CRC32 checksum of the entire original transaction for end-to-end integrity verification.

4. Gungnir feeds these frames to JS8Call via its local UDP API. JS8Call modulates them into audio tones using an FT8-derived protocol, and your radio transmits those tones over the air on HF frequencies — typically the 40-meter band around 7.078 MHz.

5. Somewhere else — possibly hundreds or thousands of miles away — a volunteer gateway operator is running JS8Call and Gungnir in gateway mode. Their JS8Call decodes the signal and passes the frames to Gungnir via UDP.

6. The gateway's Gungnir instance reassembles the chunks in order, verifies every CRC8 and the final CRC32, decompresses the data, and recovers the original raw transaction hex.

7. The gateway broadcasts the transaction to the Bitcoin network — either through the mempool.space public API or through its own local Bitcoin Core node.

8. The gateway sends an ACK back over JS8Call with the first 8 characters of the transaction ID, confirming to the sender that their Bitcoin transaction has been broadcast and will be mined into a block.

### Why JS8Call?

JS8Call is a digital communication mode for amateur radio created by Jordan Sherer, KN4CRD. It's built on the same WSJT modulation technology as FT8, which means it can decode signals at -24 dB signal-to-noise ratio — that's a signal buried so deep in noise that you literally cannot hear it. Your ears hear static. The software pulls data out of it.

JS8Call adds keyboard-to-keyboard messaging on top of this weak-signal capability. It supports directed messages (send to a specific callsign), automatic acknowledgments, and a local UDP API that other software can use to send and receive messages programmatically.

This combination — extreme weak-signal performance plus a programmable API — makes JS8Call the ideal transport for Gungnir. A 20-watt signal on 40 meters with a simple wire antenna can be decoded across an entire continent under decent propagation conditions. Under poor conditions, a relay operator partway between sender and gateway can extend the range.

### Transaction Size and Timing

A typical simple Bitcoin transaction — one input, two outputs, SegWit — is about 110 bytes. After compression and base64 encoding, this becomes roughly 84 characters, which fits in 2 data frames plus an END frame.

At JS8Call Normal speed (15 seconds per frame), the complete transmission takes about 45-60 seconds including thermal cooldown pauses to protect the radio's power amplifier. At Turbo speed with a robust base station radio, this drops to about 20 seconds.

More complex transactions with many inputs will be larger and take longer. Gungnir warns if a transaction would exceed 15 chunks, which would represent several minutes of airtime.

### Relay Nodes

Gungnir supports multi-hop relay chains. A relay node is a station between the sender and the gateway that receives Gungnir frames and retransmits them to the next hop. The relay doesn't decode the transaction, doesn't need internet access, and doesn't need to know anything about Bitcoin. It's a dumb pipe with a callsign — exactly like a Bitcoin relay node that forwards transactions without mining them.

This extends Gungnir's range through areas where direct propagation between sender and gateway isn't possible. A sender in a valley could relay through a station on a hilltop to reach a gateway in the next state.

---

## The Origin Story

In 2016, Brandon Todd worked with another amateur radio operator to manually relay a Bitcoin transaction over VHF radio using FLDIGI (a general-purpose digital mode program) and Armory wallets. They encoded the transaction by hand, transmitted it character by character, and reassembled it on the other end. It worked — but it was slow, manual, error-prone, and limited to VHF line-of-sight range (maybe 50 miles with good antennas).

Three years later, in February 2019, Rodolfo Novak (NVK), the founder of Coinkite, publicly transmitted a Bitcoin brain wallet over JS8Call on the 40-meter HF band from Toronto to Michigan. The transmission was widely covered by cryptocurrency media, discussed by Nick Szabo on Twitter, and presented as a proof of concept for Bitcoin's resilience. NVK's transmission made international news.

But NVK's transmission was also manual — a one-off demonstration, not a tool anyone could use. And the 2016 experiment predated it by three years but was never publicized.

Gungnir automates the entire process that both experiments proved was possible. It handles the encoding, chunking, error detection, reassembly, and broadcast without human intervention beyond pasting in the transaction and pressing enter. It runs on HF for continental range instead of VHF line-of-sight. And it's designed as infrastructure — gateway operators run it as a service, the way APRS iGate operators and Winlink nodes serve the ham radio community today.

---

## The Bitcoin Analogy

If you understand how the Bitcoin network works, you already understand Gungnir. The architecture is structurally identical:

A Bitcoin wallet signs transactions and submits them to the network. A Gungnir sender signs transactions offline and submits them over RF.

A Bitcoin relay node receives transactions, validates them, and forwards them to other nodes. It never mines, never holds funds. A Gungnir relay node receives frames, buffers them, and forwards them to the next hop. It never decodes the transaction, never touches funds.

A Bitcoin miner constructs blocks and writes to the blockchain — the final step where data becomes permanent. A Gungnir gateway broadcasts the transaction to the mempool — the final step where the transaction enters the Bitcoin network.

The sender's private keys never leave their device. Relay and gateway operators never see keys, never control funds. They're just passing data forward. The same way running a Bitcoin node strengthens the Bitcoin network, running a Gungnir gateway strengthens the Gungnir network. More gateways mean more redundancy, more geographic coverage, and more resilience.

---

## Security Model

### What's Protected

Bitcoin transactions are cryptographically self-securing. The ECDSA or Schnorr signature in the transaction proves that the holder of the private key authorized the spend. This signature cannot be forged, modified, or reversed by anyone who intercepts the transaction in transit.

If someone captures your Gungnir transmission off the air and tries to rebroadcast it, nothing happens — Bitcoin nodes reject duplicate transactions. If someone modifies a single byte, the signature becomes invalid and the network rejects it. The transaction is its own armor.

### What's Not Protected

Privacy. Amateur radio requires station identification. Your callsign is in every transmission, and callsigns are linked to your legal name and address in the FCC's public database. Anyone monitoring the frequency sees that your callsign sent a Bitcoin transaction. The transaction data itself — addresses, amounts — is also visible over the air, though it will be public on the blockchain within minutes anyway.

Gungnir is explicitly not a privacy tool. It's a last-resort communication channel for when the alternative is not being able to transact at all. If you have internet access and want privacy, use Tor, run your own node, use CoinJoin. Gungnir should be chosen over nothing, not over better options.

### The Gateway Trust Model

You're trusting the gateway operator to actually broadcast your transaction and not just pocket the data. This is the same trust model as using someone else's Electrum server or submitting a transaction through a public API like mempool.space — you're trusting infrastructure you don't control.

The mitigation is the same as in the broader ham radio community: reputation. Callsigns are permanent identities. A gateway operator who dropped transactions or misused data would be identified and blacklisted. The planned multi-gateway feature will allow sending to multiple gateways simultaneously, so no single operator is a point of failure or trust.

---

## FCC and Legal Landscape

### The Pecuniary Interest Question

FCC Part 97.113(a)(3) prohibits transmissions "in which the station licensee or control operator has a pecuniary interest." Sending a Bitcoin transaction could be argued to involve pecuniary interest since you're literally moving money.

This has never been tested or ruled on by the FCC. The counterargument: the operator is transmitting a pre-signed data blob, not conducting commerce or negotiating a business deal over the air. The pecuniary interest rule targets commercial radio operations — using amateur frequencies to run a business — not the transmission of encoded data that happens to contain financial instructions.

The strongest precedent is NVK's 2019 transmission, which was publicly announced, widely covered by media, and explicitly identified as a Bitcoin transaction over amateur radio. The FCC took no action.

Gateway operators have even less regulatory exposure — they're relaying data for another station, similar to an APRS digipeater or a Winlink relay node.

### Encryption

There is none, by design. FCC Part 97 prohibits encryption on amateur frequencies. Gungnir uses encoding (base64, hex) but not encryption. The transaction data is publicly verifiable on the blockchain. This is the same category as every other digital mode — FT8, PSK31, and JS8Call itself all use encoding.

### The Samourai Wallet Distinction

In 2024, the founders of Samourai Wallet were charged with operating an unlicensed money transmitting business and conspiracy to commit money laundering. Samourai's core features were specifically designed to obscure the origin and destination of funds — CoinJoin mixing, Ricochet transaction layering, and a centralized server that coordinated these privacy features.

Gungnir has none of these characteristics. It's a transport layer, not a financial service. It never has custody of funds, doesn't modify transactions, doesn't mix or pool anything, doesn't obscure origins or destinations, and has no business model. Gateway operators are amateur radio volunteers, not financial service providers. The distinction is fundamental — Gungnir is closer to a modem than a money transmitter.

---

## What This Means for the World

### Completing Bitcoin's Promise

Bitcoin was designed to be censorship-resistant money. But censorship resistance requires more than a protocol — it requires the ability to reach the protocol from anywhere, under any conditions. Right now, the entire world's access to Bitcoin depends on internet infrastructure that governments and natural disasters can disable.

Gungnir closes that gap. It means that anywhere on Earth where someone has a radio and a signing key, they can transact in Bitcoin. The ionosphere becomes the network layer of last resort — and unlike the internet, nobody controls it.

### Disaster Response

After a major disaster, the financial system is often the second thing to fail after communications. ATMs go offline. Card readers stop working. Banks close. Cash runs out. People need to buy fuel, food, medicine, and transportation, and the systems they normally use to pay for these things are down.

Ham radio operators are always among the first responders in disaster scenarios — they provide the communication backbone when everything else fails. Gungnir adds financial capability to that communication backbone. A ham operator with a Gungnir gateway can enable an entire community to transact in Bitcoin while waiting for internet infrastructure to be restored.

### Censorship Resistance in Practice

The theoretical censorship resistance of Bitcoin is tested every time a government shuts down the internet. Until now, those shutdowns effectively disabled Bitcoin along with everything else. Gungnir changes the calculus: shutting down the internet no longer shuts down Bitcoin, because Bitcoin transactions can route through a medium that has no off switch.

This doesn't require mass adoption. A single gateway operator in a neighboring country — or even a single ham with a decent antenna anywhere within HF propagation range — is enough to bridge the gap. One gateway is enough. And unlike internet infrastructure, you can't find and shut down every HF radio in a country. The signals are everywhere, decoded from noise levels you can't hear, transmitted from antennas that can be a piece of wire thrown over a tree branch.

### Machine-to-Machine Payments

Looking further ahead, Gungnir's architecture supports autonomous devices in remote locations. A solar-powered weather station with an HF radio and a signing key could settle payments — for data subscriptions, maintenance contracts, or resource allocation — without ever connecting to the internet. Agricultural sensors, maritime buoys, remote mining equipment, scientific instruments in the field — any device that can sign a transaction and key a radio can participate in the Bitcoin economy through Gungnir.

---

## The Network Effect

Gungnir gets more resilient as more people participate, exactly like Bitcoin itself.

One gateway covers one geographic area. Ten gateways cover a continent. Relay operators extend range into dead zones. Multiple gateways accepting the same transaction provide redundancy — if one goes down, the others are still there.

The barrier to entry for running a gateway is low: a computer with internet access, a radio, JS8Call, and Gungnir. Many ham operators already have this equipment and leave their stations running 24/7 for other digital modes. Adding Gungnir is installing Python and running one command.

The barrier for relay operators is even lower: no internet needed, no Bitcoin knowledge needed. Just Python, JS8Call, and a radio. You're strengthening the network by being a node, the same way running a Bitcoin relay node strengthens that network.

---

## Current Status (March 2026)

The MVP is built and tested:
- Full protocol: encode, compress, chunk, frame, CRC8 per chunk, CRC32 end-to-end
- Sender, gateway, and relay modes all working
- JS8Call UDP API integration confirmed working
- Loopback testing mode for development without radio hardware
- 47 unit tests passing
- End-to-end integration test passing through JS8Call's actual UDP API

Next steps:
- Live over-the-air test on 40 meters (pending testnet coins from faucet)
- Desktop GUI for non-technical operators
- Gateway discovery beacons
- Multi-gateway redundancy
- Community outreach to ham radio and Bitcoin communities

---

## The Bottom Line

A $200 radio, a piece of wire for an antenna, a car battery for power, and a laptop with Sparrow and Gungnir installed. That's the entire uplink. No cell towers. No ISPs. No DNS servers. No submarine cables. No satellites. No infrastructure of any kind beyond what you carry with you.

The ionosphere is free, global, and unkillable. Bitcoin transactions are cryptographically self-securing and transport-agnostic. Gungnir connects these two facts into a tool that makes Bitcoin's censorship resistance promise actually real — not just in theory, not just when the internet is working, but always, everywhere, no matter what.

That's what Gungnir does for the world. It makes Bitcoin unkillable in practice, not just in theory. It gives Odin's spear a target it can always reach.
