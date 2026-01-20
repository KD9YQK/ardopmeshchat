# RF Mesh Chat – Test Data Entry Sheet

**Purpose:**
This sheet is used to **record results only** while running the *RF Mesh Chat — Full Program Test Guide*.
It does **not** explain tests. It is purely for data capture.

Fill out one sheet per test session.

---

## Test Session Information

Date:

Start Time:

End Time:

Operator Name / Callsign:

Location / Station:

Program Version / Commit:

Test Kit Used (circle one):

* Kit A (Single Station)
* Kit B (Two Stations)
* Kit C (Three Stations)

Devices Used:

* Node A:
* Node B:
* Node C:

Link Type(s) Used (check all that apply):
☐ ARDOP TCP
☐ TCP Mesh
☐ Multiplex

---

## Quick Environment Check

GUI Mode Used?   ☐ Yes ☐ No

Headless Mode Used?   ☐ Yes ☐ No

Any configuration changes made before test?   ☐ No ☐ Yes (describe):

---

## Test Results Log

> Mark **PASS** or **FAIL** only.
> If FAIL, briefly describe what was observed.

| Test ID                     | PASS | FAIL | Brief Observation / Notes |
| --------------------------- | ---- | ---- | ------------------------- |
| 5.1 GUI Startup             | ☐    | ☐    |                           |
| 5.2 Headless Startup        | ☐    | ☐    |                           |
| 5.3 Restart Behavior        | ☐    | ☐    |                           |
| 6.1 Local Message           | ☐    | ☐    |                           |
| 6.2 Persistence             | ☐    | ☐    |                           |
| 7.1 Discovery               | ☐    | ☐    |                           |
| 7.2 Peer Expiry             | ☐    | ☐    |                           |
| 8.1 A→B Message             | ☐    | ☐    |                           |
| 8.2 B→A Message             | ☐    | ☐    |                           |
| 8.3 Message Integrity       | ☐    | ☐    |                           |
| 9.1 Multi-hop Discovery     | ☐    | ☐    |                           |
| 9.2 A→C Forwarding          | ☐    | ☐    |                           |
| 9.3 TTL / Loop Safety       | ☐    | ☐    |                           |
| 10.1 Deduplication          | ☐    | ☐    |                           |
| 11.1 Offline Sync           | ☐    | ☐    |                           |
| 12.1 Store & Forward        | ☐    | ☐    |                           |
| 13.1 Compression            | ☐    | ☐    |                           |
| 14.1 Plaintext Default      | ☐    | ☐    |                           |
| 15.1 Plugin Load            | ☐    | ☐    |                           |
| 15.2 Plugin Isolation       | ☐    | ☐    |                           |
| 16.1 GUI Peer Updates       | ☐    | ☐    |                           |
| 16.2 GUI Message Order      | ☐    | ☐    |                           |
| 17.1 Link Drop Recovery     | ☐    | ☐    |                           |
| 17.2 Restart During Use     | ☐    | ☐    |                           |

---

## Failure Detail Section (use only if FAIL occurred)

Failure Test ID:

What step failed:

What was expected:

What actually happened:

Time observed:

Screenshots taken? ☐ Yes ☐ No

Logs saved? ☐ Yes ☐ No

Log filename(s):

---

## Overall Assessment

Did the system successfully pass this test session?
☐ YES – No blocking issues
☐ PARTIAL – Usable with issues
☐ NO – Blocking failures present

Summary of concerns:

---

## Operator Sign-off

Name / Callsign:

Signature:

Date:

---

## Developer Review (optional)

Reviewed by:

Date:

Action required? ☐ No ☐ Yes

Action notes / Issue references:

---

**Important:**
Do not attempt to troubleshoot during testing. Record observations only.
