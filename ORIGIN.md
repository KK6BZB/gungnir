# Gungnir — Origin Story & Background
### Why This Exists and Why I'm the One Building It

---

## The Short Version

I was sending Bitcoin over amateur radio in 2016 — three years before NVK's "historic first" JS8Call transaction made international crypto news in 2019. Nobody wrote about it because I wasn't on Twitter with a following. The difference between me and the people who got credit was distribution, not innovation.

Gungnir is the tool I wish existed back then.

---

## The 2016 Experiment

In 2016, I worked with another ham operator to relay Bitcoin transactions over VHF radio using FLDIGI and Armory wallets. Armory had this notoriously clunky offline signing workflow — you had to split the wallet into a watching-only copy (online) and a signing copy (offline/cold storage), then shuttle unsigned and signed transaction blobs back and forth between them.

We used FLDIGI as the transport layer, manually sending the unsigned transaction data over VHF from the online machine to the offline signing machine at the other operator's station, signing it there, and sending the signed blob back over radio for broadcast to the network.

It worked. It was manual, tedious, and short-range (VHF is line-of-sight). But it proved the concept: Bitcoin transactions can move over amateur radio without touching the internet.

Nobody documented it. Nobody wrote it up. It was just two hams messing around with Bitcoin and radios.

---

## What Changed Between Then and Now

**Radio side:** JS8Call (and now JS8Call-improved) didn't exist in 2016. FLDIGI works fine under decent conditions, but JS8Call's FT8-derived modulation gives you weak-signal performance that FLDIGI can't touch. We're talking -24dB SNR decoding — signals buried in noise that you can't even hear. And it runs on HF, which means ionospheric propagation — continental range, not line-of-sight. Coast to coast on 5 watts.

**Bitcoin side:** Modern wallets like Sparrow and Electrum handle offline signing in a single step. No more Armory two-machine shuffle. You build the transaction, specify everything (amount, recipient, change, fee), sign it, and get a complete raw hex blob ready for broadcast. One step, fully offline.

**The gap:** Despite both sides getting dramatically better, nobody has built the bridge. Every BTC-over-radio experiment since 2016 has been a one-off hack — NVK sending a brain wallet passphrase (terrible OPSEC), goTenna/TxTenna on short-range VHF mesh (now dead — Samourai's founders arrested, domain seized by FBI). There is no purpose-built, reliable tool for encoding a signed Bitcoin transaction, chunking it for radio transport, and reassembling it for broadcast on the other end.

That's Gungnir.

---

## Why Me

The Venn diagram of people who are:
- Licensed amateur radio operators (KK6BZB, General class)
- Bitcoin maximalists with 12 years of trading experience
- Experienced enough to have actually sent BTC over radio before
- Product builders who can ship software

...is vanishingly small. I'm in it.

I'm not a DSP engineer. I'm not going to build a new digital mode or write Fortran signal processing code. I don't need to — JS8Call-improved already solved the hard radio problem. What I'm building is the application layer: the Bitcoin-specific encoding, chunking, framing, reassembly, and broadcast pipeline that sits on top of JS8Call's transport.

This is the same build pattern as everything else I've done at Valhalla Systems: identify the gap, build the bridge, ship the tool.

---

## The Bigger Picture

Bitcoin and amateur radio share the same DNA:
- Decentralized
- Permissionless
- Censorship-resistant
- Run by volunteers who believe the infrastructure matters
- Both communities exist because someone decided that depending on centralized gatekeepers for something this important was unacceptable

Gungnir doesn't force these two worlds together. They were always building toward the same thing. This project just connects them.

When the internet goes down — whether from a natural disaster, government censorship, or infrastructure failure — Bitcoin doesn't stop working. The transactions are still valid. The blockchain is still there. The only thing missing is a way to get your signed transaction to the network.

Gungnir is that way. Odin's spear. It never misses its target.

---

## Personal Context

I'm 50. I live in a camper in Tucson. I started rock climbing at 47 and now project V7. I was homeless as a teenager and have 21 years clean from heroin. I taught myself to build software through AI-assisted development. I don't have a CS degree. I have resilience, domain expertise in two niche communities that almost nobody bridges, and the ability to ship.

This is the project that connects all of it.

---

*Brandon Todd, KK6BZB*
*Valhalla Systems*
*2026*
