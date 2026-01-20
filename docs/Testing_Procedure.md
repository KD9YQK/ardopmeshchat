# RF Mesh Chat — Full Program Test Guide (Operator + Developer)

This is a **complete, step-by-step test guide** for the RF Mesh Chat System.

It’s written for two audiences at once:

* **Radio operators (non-programmers):** follow the steps, observe results, record pass/fail.
* **Developers:** optional “deep checks” (logs/DB) are included to confirm the internals.

No prior knowledge of meshes, routing, or programming is required to **run** the tests.

---

## 0) Plain-English Glossary (read once)

* **Node**: One running copy of the program on a computer/radio station.
* **Peer**: Another node your node can see/talk to.
* **Link**: The physical/transport connection between nodes (ARDOP TCP, TCP mesh, multiplex).
* **Discovery**: Nodes automatically noticing each other.
* **Route**: The path messages take to reach a peer (may go through other nodes).
* **Hop**: One step in a route. Direct = 1 hop. Through a middle node = 2 hops.
* **Forwarding**: A middle node relays a message between two nodes that can’t reach directly.
* **Sync**: Catching up on messages you missed while offline.
* **Store-and-forward**: Holding messages for an offline peer, then delivering when it returns.
* **Deduplication**: Dropping duplicate copies of the same message.
* **TTL** (time-to-live): A countdown that prevents messages from bouncing forever.

---

## 1) What “Testing the Entire Program” Means

To test the whole program, we verify:

1. It starts and runs reliably in **GUI and headless** modes.
2. Nodes **discover peers** automatically.
3. Messages are delivered:

   * Direct (A → B)
   * Multi-hop (A → C through B)
4. Messages are not duplicated and don’t loop.
5. Messages are stored in **SQLite** and survive restarts.
6. If a node is offline, the system **syncs or store-forwards** correctly when it returns.
7. Multiple link types (ARDOP, TCP mesh, multiplex) work as expected.
8. Optional subsystems (compression/encryption hooks/plugins) behave safely and don’t break defaults.
9. Recovery from real-world failures (dropped links, restarts) is clean.

---

## 2) Test Kits (choose the one you can run)

### Kit A — Single Station (1 computer)

Use this if you only have one machine available.

* Confirms: startup, local chat/storage, basic stability.
* Does NOT fully confirm: routing, multi-hop, store-forward.

### Kit B — Two Stations (2 computers or 2 instances)

Use this for a proper field verification.

* Confirms: discovery, direct messaging, persistence, basic sync.

### Kit C — Three Stations (best / full coverage)

Use this to verify multi-hop and forwarding.

* Confirms: routing, forwarding, TTL, best-next-hop.

---

## 3) Preflight Setup (Operators)

### 3.1 What you need

* Two or three computers (or devices) if possible.
* Program installed on each.
* The station/radio link(s) set up as usual (ARDOP TCP and/or TCP mesh).

### 3.2 What you should record before starting

Fill this in at the top of your test sheet:

* Date/Time:
* Operator name:
* Devices used (A/B/C):
* Link type(s) used (ARDOP / TCP mesh / Multiplex):
* Program version/commit:

### 3.3 Standard test message format (important)

Always send messages that include the test ID so you can recognize them:

* `T<Section>.<Test>-<FromNode>-<ShortText>`

  * Example: `T6.2-A-hello`

---

## 4) How to Capture Results (Operators)

For every test, mark:

* **PASS**: expected result happened.
* **FAIL**: expected result did not happen.

If FAIL, write:

* What you did (step number)
* What you saw instead
* Screenshot(s) if GUI
* Save log file(s) if you have them

Do **not** attempt to diagnose. Just record.

---

## 5) Startup & Basic Health (All Kits)

### 5.1 Start in GUI mode

* **What we’re testing:** The program launches and UI is usable.
* **How (steps):**

  1. Start the GUI application.
  2. Wait up to 30 seconds.
  3. Look for a node identity shown somewhere (node name/ID).
* **Expected result:**

  * GUI opens without errors.
  * You see your local node identity and a status area.
* **Developer deep checks (optional):**

  * Logs show startup sequence completed; node ID loaded.

☐ PASS / ☐ FAIL   Notes:

### 5.2 Start in headless/daemon mode

* **What:** Core runs without GUI.
* **How:** Start the daemon/CLI start command used at your site.
* **Expected:** Process stays running; logs show it is active.
* **Developer deep checks:** Confirm no GUI imports; no crash traces.

☐ PASS / ☐ FAIL   Notes:

### 5.3 Clean shutdown and restart

* **What:** Restart safety (prevents DB corruption and “ghost state”).
* **How:**

  1. Stop the program normally.
  2. Start it again.
* **Expected:** It comes back without errors; your node identity remains the same.

☐ PASS / ☐ FAIL   Notes:

---

## 6) Local Chat & Storage (Kit A minimum)

### 6.1 Send a message locally (loopback/self)

* **What:** Chat pipeline + persistence without network.
* **How:** Send `T6.1-A-local` to your local channel/self as your UI allows.
* **Expected:** Message appears in the chat view and remains after restart.
* **Developer deep checks:** DB contains the message row.

☐ PASS / ☐ FAIL   Notes:

### 6.2 Persistence across restart

* **What:** SQLite durability.
* **How:**

  1. Confirm `T6.1-A-local` is visible.
  2. Restart the program.
  3. Re-open history.
* **Expected:** The message is still present.

☐ PASS / ☐ FAIL   Notes:

---

## 7) Discovery (Kits B/C)

### 7.1 Two-node discovery

* **What:** Nodes automatically see each other.
* **How:**

  1. Start Node A.
  2. Start Node B.
  3. Wait up to 2 minutes.
* **Expected:**

  * A shows B as a peer (online/available).
  * B shows A as a peer.
* **What to write if it fails:** Do you see “link down” or no peers at all?

☐ PASS / ☐ FAIL   Notes:

### 7.2 Peer expiry (stale peer disappears)

* **What:** Offline detection.
* **How:**

  1. With A and B visible to each other, stop Node B.
  2. Wait longer than your configured peer timeout (use 3–5 minutes if unknown).
* **Expected:** A marks B offline/disappears.

☐ PASS / ☐ FAIL   Notes:

---

## 8) Direct Messaging (Kits B/C)

### 8.1 A → B message delivery

* **What:** Core send/receive path over the link.
* **How:**

  1. On Node A, send: `T8.1-A-toB` addressed to Node B.
  2. Watch Node B.
* **Expected:**

  * Node B displays the exact message once.
  * If there’s a timestamp, it’s reasonable.

☐ PASS / ☐ FAIL   Notes:

### 8.2 B → A reply

* **What:** Bidirectional traffic.
* **How:** On Node B, send `T8.2-B-toA` back.
* **Expected:** A receives it once.

☐ PASS / ☐ FAIL   Notes:

### 8.3 Message integrity test (special characters)

* **What:** No corruption/truncation.
* **How:** Send a message containing:

  * punctuation: `!@#$%^&*()`
  * unicode: `✓ æ Ω 漢字`
  * a longer paragraph (copy/paste 2–3 sentences)
* **Expected:** Receiver shows exactly what was sent.

☐ PASS / ☐ FAIL   Notes:

---

## 9) Multi-hop Routing & Forwarding (Kit C)

**Topology goal:** A can talk to B, B can talk to C, but A cannot directly talk to C.

### 9.1 Multi-hop discovery

* **What:** A learns about C via B.
* **How:** Start A, B, C in the A↔B↔C arrangement. Wait up to 2 minutes.
* **Expected:** A lists C as a peer with hop count 2 (or indirect).

☐ PASS / ☐ FAIL   Notes:

### 9.2 A → C message via B

* **What:** Forwarding actually works.
* **How:**

  1. On A, send `T9.2-A-toC` to C.
  2. Watch C.
* **Expected:** C receives once.
* **Developer deep checks:** B logs a forward action; TTL decremented.

☐ PASS / ☐ FAIL   Notes:

### 9.3 TTL safety (prevents infinite bouncing)

* **What:** Loop protection.
* **How (simple operator version):**

  1. Temporarily create an odd topology (if possible) where two routes exist.
  2. Send one message and confirm you do NOT see it repeating.
* **Expected:** No repeating duplicate arrivals.
* **Developer deep checks:** TTL reaches zero and is discarded if looping occurs.

☐ PASS / ☐ FAIL   Notes:

---

## 10) Deduplication (especially with Multiplex)

### 10.1 “Exactly once” delivery

* **What:** Duplicate packets don’t become duplicate chat messages.
* **How:**

  1. Ensure multiplex is enabled (if your site uses it) with 2 underlying links.
  2. Send `T10.1-A-once` from A to B.
* **Expected:** B sees it exactly once.
* **Developer deep checks:** Logs show dedupe drops.

☐ PASS / ☐ FAIL   Notes:

---

## 11) Sync (Catch Up After Being Offline)

### 11.1 Offline then sync on return

* **What:** A peer that missed messages can catch up.
* **How:**

  1. Start A and B.
  2. Stop B (fully offline).
  3. From A, send 3 messages destined for B:

     * `T11.1-A-m1`
     * `T11.1-A-m2`
     * `T11.1-A-m3`
  4. Start B again.
* **Expected:** B eventually receives the missing messages (may take time depending on link).
* **Developer deep checks:** B detects a gap and requests missing messages; idempotent behavior (no duplicates).

☐ PASS / ☐ FAIL   Notes:

---

## 12) Store-and-Forward (If Enabled)

### 12.1 Queue messages for offline peer

* **What:** Messages are held (not lost) when peer is offline.
* **How:**

  1. Take B offline.
  2. From A, send `T12.1-A-queued1` and `T12.1-A-queued2` to B.
  3. Bring B back online.
* **Expected:** B receives both, once each, after it returns.
* **Developer deep checks:** Queue persists; drains on reconnection.

☐ PASS / ☐ FAIL   Notes:

---

## 13) Compression (If Available/Enabled)

### 13.1 Compression off vs on

* **What:** Config toggles work; messages remain readable.
* **How:**

  1. Run with compression OFF; send `T13.1-A-off` A→B.
  2. Run with compression ON; send `T13.1-A-on` A→B.
* **Expected:** B receives both messages correctly.
* **Developer deep checks:** Logs indicate compression used only in ON case.

☐ PASS / ☐ FAIL   Notes:

---

## 14) Encryption Hooks (Must be Disabled by Default)

### 14.1 Default is plaintext

* **What:** No accidental encryption.
* **How:** Use default config; send `T14.1-A-plain`.
* **Expected:** Receiver can read it; no special steps required.

☐ PASS / ☐ FAIL   Notes:

(Only run “encryption enabled” tests if your project explicitly supports and documents it.)

---

## 15) Plugins & Event Hooks (If Present)

### 15.1 Plugin loads and doesn’t crash core

* **What:** Plugins are optional and safe.
* **How:** Start node with known plugin enabled.
* **Expected:** System runs normally; plugin announces itself (UI/log) if designed to.

☐ PASS / ☐ FAIL   Notes:

### 15.2 Plugin failure isolation

* **What:** A broken plugin won’t take down the network.
* **How:** Enable a test plugin that intentionally errors (developer-controlled).
* **Expected:** Error logged; messaging still works.

☐ PASS / ☐ FAIL   Notes:

---

## 16) GUI-Specific Behavior (Operators)

### 16.1 Peer list updates live

* **What:** Discovery propagates to UI.
* **How:** Start/stop Node B and watch Node A’s GUI.
* **Expected:** Peer appears then later goes offline.

☐ PASS / ☐ FAIL   Notes:

### 16.2 Incoming messages appear once and in order

* **What:** UI display correctness.
* **How:** Send 5 messages in a row from B→A.
* **Expected:** A displays all 5, once each, in correct order.

☐ PASS / ☐ FAIL   Notes:

---

## 17) Failure & Recovery (Real-World Robustness)

### 17.1 Drop link abruptly

* **What:** Handles RF/TCP disruptions gracefully.
* **How:** While A and B are connected, unplug/disconnect the link.
* **Expected:** Peer goes offline; system doesn’t crash; reconnect works.

☐ PASS / ☐ FAIL   Notes:

### 17.2 Restart during activity

* **What:** Safe restart while messages exist.
* **How:** While sending messages, restart Node B.
* **Expected:** Program restarts cleanly; no corrupted history; messages resume.

☐ PASS / ☐ FAIL   Notes:

---

## 18) Final Sign-Off

System passes the full test when:

* All required tests for your chosen kit (A/B/C) are PASS
* No crashes occurred
* No duplicate message delivery was observed
* Messages persist across restarts

### Results summary

* Kit used: A / B / C
* Total PASS:
* Total FAIL:
* Failures attached (screenshots/logs):

---

## Appendix A — Developer Evidence (Optional)

Operators can skip this entire appendix.

If you’re a developer verifying internals, for any FAIL capture:

* Send/receive message IDs in logs
* Peer table / routing table snapshot
* Dedupe drops (if multiplex)
* Sync requests and responses
* DB row count before/after sync

(Exact commands/paths depend on your repo and deployment.)
