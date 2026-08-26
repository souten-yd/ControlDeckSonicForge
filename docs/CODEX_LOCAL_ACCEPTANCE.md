# Codex Local Acceptance and Merge Runbook

Status: normative operator runbook  
Date: 2026-08-25

This document defines the local-machine acceptance gate for SonicForge and its generic ControlDeck integration changes.

**Mandatory companion:** whenever `SF受入確認` or `SF受入マージ` is invoked, also read and apply `docs/CODEX_LOCAL_ACCEPTANCE_FINAL.md`. The base runbook and that addendum together are normative. Where the addendum explicitly supersedes an older detail in this file, use the addendum.

## 1. Short commands

When the user says exactly or substantially:

### `SF受入確認`

Execute this runbook through the local acceptance report.

- Do **not** merge any PR.
- Run the required local checks.
- Fix defects found when the fix is clearly within scope.
- Re-run only the affected local checks while iterating.
- At the end, run the complete local acceptance set once.
- Report PASS / FAIL / NOT TESTED with evidence.

### `SF受入マージ`

Execute the same local acceptance procedure, then merge only when all required gates pass.

- Do not assume an older result is still valid after code changes.
- Re-run the relevant complete local acceptance set against the exact heads to be merged.
- Do not merge when any required item is FAIL, when a critical item is NOT TESTED, or when the working tree contains unreviewed changes.
- If all gates pass, run the intentionally batched CI gate once where configured, wait for the result, then merge in dependency order.
- If CI is unavailable but the repository has no mandatory CI requirement, report that explicitly before merge and follow the user instruction for the current session.

## 2. Merge policy

Local functional validation is the primary promotion gate.

Never merge merely because:

- code compiles;
- unit tests pass;
- a PR is reviewable;
- a focused test passed previously;
- GitHub reports no conflicts.

The expected order is:

```text
implementation
 -> focused local tests while iterating
 -> full local acceptance on target hardware
 -> one batched CI run for the milestone
 -> inspect PR diff / unresolved comments / mergeability
 -> merge dependency PRs
 -> rebase or update dependent PR if needed
 -> short post-merge smoke test
```

Current dependency direction is:

```text
ControlDeck generic Host contracts
 -> SonicForge use of those contracts
```

If a SonicForge PR depends on an unmerged ControlDeck PR, merge the generic ControlDeck contract first after both sides have been validated together locally. Then update/rebase the SonicForge branch if required and re-run the affected smoke tests before merging SonicForge.

Publisher-signature Release Bundle work is a separate generic ControlDeck Host concern and must not be mixed into SonicForge-specific Host logic.

## 3. Repositories / branches / PRs to inspect

Do not trust these identifiers blindly; confirm the current state before acting.

Expected working set as of this runbook revision:

```text
ControlDeckSonicForge
  branch: impl/full-platform-baseline
  PR: #1

ControlDeck
  generic publisher-signature PR: #239
  generic AI/media gateway PR: #240
```

Before tests:

1. fetch current remotes;
2. confirm exact branch heads and PR heads;
3. confirm working trees are clean or deliberately capture local modifications;
4. record commit SHAs in the acceptance report;
5. inspect PR changed files and unresolved review comments;
6. do not merge a stale branch accidentally.

## 4. Test philosophy

The product is primarily local-first. Do not add artificial authentication or duration restrictions merely to make tests easy.

Basic local operations should work without user-facing authentication:

```text
ASR
TTS
SFX
Music
local audio pipelines
local/live voice I/O
meeting/dictation capture
```

ControlDeck credentials remain an internal boundary only when a path actually uses Host-owned capabilities such as:

```text
ControlDeck LLM router
Host Jobs
Resource Broker
scoped project/file grants
project output commit
Add-on device relay
```

Do not expose ControlDeck service tokens to M5/mobile clients.

## 5. Static / unit gate — SonicForge

From the SonicForge repository, create/use the normal development venv and run the full lightweight suite.

At minimum:

```bash
python -m compileall backend worker_packs tests
pytest -q
```

Also verify:

- public schemas validate;
- `addon.json` validates against the current ControlDeck Add-on contract;
- no `shell=True`;
- worker output containment tests pass;
- release signature negative tests pass;
- Browser Bridge names remain current (`host.file.pick`, etc.);
- embedded proxy-relative HTTP/WS paths pass tests;
- local unauthenticated APIs pass tests;
- pipeline type mismatch tests pass;
- Resource Broker stage-order tests pass;
- live PTT and ASR-only dictation tests pass;
- audio delivery profile tests pass;
- SFX prompt-normalization provenance tests pass.

Any failure blocks merge until explained and fixed or explicitly removed from required scope by the user.

## 6. Static / unit gate — ControlDeck

Run the normal ControlDeck backend test gate plus all directly affected test modules.

At minimum include tests for:

```text
Add-on contract parsing
Add-on Runtime auth
Add-on Runtime AI complete / stream / release
AI residency hold create / renew / release / expiry
Generic Gateway discovery
Resource Broker
Device pairing / device relay
Release Bundle signature verification
```

Confirm existing MediaForge behavior is not broken by generic Host changes.

Do not weaken existing security/capability checks to make SonicForge tests pass.

## 7. Real Speech Essentials gate

Use actual installed models, not fake workers.

### ASR

Test at least:

- Japanese speech;
- English speech;
- mixed Japanese/English speech where practical;
- short utterance;
- multi-minute audio;
- a long-form recording path used for meeting/dictation.

Record:

```text
model/runtime
backend/device
input duration
wall time
real-time factor
first partial latency if streaming
final latency
observed transcription issues
```

### TTS

Test at least:

- Japanese;
- English;
- selected built-in voice;
- logical voice profile;
- voice-clone path only with a permitted test reference;
- repeated turns using the same live session.

Record time to first playable audio and total generation time.

## 8. Voice-chat latency acceptance

The voice-chat path is not accepted merely because the final WAV is correct.

Target architecture:

```text
speech input
 -> ASR partial/final
 -> ControlDeck streaming LLM
 -> Japanese/English clause chunker
 -> TTS chunk generation
 -> immediate playback of first completed chunk
 -> generate the next chunk while current audio is playing
```

Measure separately:

```text
end-of-speech -> ASR final
ASR final -> first LLM text token
ASR final -> first speakable text chunk
first speakable chunk -> first TTS audio
end-of-speech -> first audible output
full response completion
```

PASS requires that the implementation does not wait for the entire LLM response and entire TTS response when streaming/chunked mode is enabled.

For turn 2 and later in the same voice session, verify that avoidable model reloads do not recur.

A test that shows Qwen TTS or ASR model cold-loading on every ordinary turn is a performance FAIL for live voice mode.

## 9. LLM / ASR / TTS residency acceptance

During a live voice session, the preferred behavior is warm coexistence when hardware capacity permits.

Verify:

1. ControlDeck LLM is held by a session-scoped residency hold.
2. SonicForge does **not** call `ai.release` after every live LLM stage while that hold is active.
3. ASR/TTS live workers remain resident/persistent across turns when selected by the live runtime.
4. Any persistent GPU worker has a matching active/renewed Resource Broker lease.
5. Batch SFX/Music work does not silently evict the active voice stack unless Broker policy explicitly decides capacity requires it.
6. Ending the live session releases residency/leases and returns to normal policy.

Warm coexistence is a preference, not permission to overcommit VRAM. If all three cannot fit, the system must report/route/queue/fallback explicitly rather than OOM-crashing.

## 10. Crash / abnormal-exit acceptance

This section is mandatory.

### SonicForge graceful shutdown

While a live voice session is active:

- stop SonicForge normally;
- persistent ASR/TTS child workers must terminate;
- SonicForge-held resource leases must be released;
- ControlDeck LLM residency hold must be released or allowed to expire promptly;
- restarting SonicForge must produce a clean service without orphan session state.

### SonicForge SIGKILL / crash

Start a voice session, warm ASR/LLM/TTS, then kill the SonicForge parent process without graceful cleanup.

PASS requires:

- persistent child workers do not remain indefinitely;
- on Linux, parent-death handling terminates child workers where implemented;
- Resource Broker lease renewals stop;
- Host lease TTL reaps abandoned leases;
- AI residency heartbeat stops;
- residency hold expires automatically after its TTL;
- ControlDeck remains healthy;
- a new SonicForge process can start and create a new voice session;
- no manual database edit is required.

Record before/after:

```text
process list
GPU memory / device state
Broker active leases
AI residency holds
SonicForge health
```

A hold or lease that can survive a dead SonicForge indefinitely is a merge-blocking FAIL.

### ControlDeck crash/restart

With SonicForge running:

- restart ControlDeck;
- Host in-memory holds may disappear safely;
- SonicForge must reconnect/re-establish Host state rather than assuming old holds remain;
- local ASR/TTS endpoints must remain usable when their path does not require Host AI/project functions;
- no stale Host credential may become a permanent blocker.

## 11. Simultaneous translation acceptance

Test both directions where models support them:

```text
Japanese speech -> ASR -> translation -> English text
Japanese speech -> ASR -> translation -> English TTS
English speech -> ASR -> translation -> Japanese text
English speech -> ASR -> translation -> Japanese TTS
```

For streaming translation, verify incremental stable segments rather than retranslating the entire accumulated transcript for every frame.

For meeting mode, store at least:

```text
segment id
start/end timestamps
source language
source text
target language
translated text
revision/finalized state
```

Translation instructions/dictionary/terminology must be injectable without exposing provider/model identity to SonicForge when using ControlDeck AI.

## 12. Meeting / minutes acceptance

A meeting is a long-lived session, not one giant in-memory PTT buffer.

Test a real long recording and verify:

- audio is spooled/bounded rather than accumulated indefinitely in RAM;
- segment transcripts are persisted incrementally;
- disconnect/reconnect does not destroy finalized transcript segments;
- a single ASR failure does not erase the whole meeting;
- final transcript can be exported;
- optional ControlDeck LLM summarization produces summary / decisions / action items;
- source transcript remains available independently of the summary;
- simultaneous translation can coexist with meeting transcription;
- no arbitrary 60-second limit applies to meeting/dictation mode.

Speaker diarization may remain optional until explicitly promoted, but the absence must be reported rather than fabricated.

## 13. Local unauthenticated API acceptance

On a trusted local configuration, verify no user-facing auth is required for the basic SonicForge functions.

Test direct local calls for:

```text
ASR from uploaded/raw audio
TTS from text
SFX generation
Music generation
local voice chat transport
meeting/dictation transport
```

Then separately verify that Host-only operations still require a valid ControlDeck execution identity:

```text
Host AI routing
project grants
project output commit
Host-managed GPU admission where required
```

Do not turn local-first into public unauthenticated Internet exposure. If binding beyond trusted LAN/Tailscale, document that as an operator deployment choice.

## 14. SFX / Music / asset generation acceptance

Exercise real model paths where installed:

- Stable Audio 3 Small-SFX CPU path;
- ACE-Step music path on the target AMD/ROCm machine;
- optional Stable Audio music fallback if installed.

Check:

- Japanese SFX prompt normalization;
- source and engine prompt provenance;
- duration controls;
- WAV master creation;
- deterministic audio inspection;
- export profiles for web/mobile/game/M5;
- project output grant commit through ControlDeck;
- OpenCode `sonic.generate` / `sonic.pipeline` invocation.

Do not claim Stable Audio GPU support if only the CPU path was validated.

## 15. M5 / device acceptance

Use the user's existing M5/edge client; SonicForge does not own or build device firmware.

PTT/server-contract baseline:

```text
pair/connect or trusted-local connect
hello/capability negotiation
PTT start
16 kHz PCM uplink
ASR
optional ControlDeck LLM
TTS
24 kHz PCM downlink
playback
next turn without full model reload
```

Check sequence gaps, Wi-Fi reconnect, bounded buffers, and playback underruns as observable through the existing client and SonicForge server logs/events.

Authentication must not make local use burdensome. Direct trusted-local SonicForge speech paths should remain possible without user-facing authentication. For the optional paired Host relay path, device credentials follow the normal ControlDeck Add-on maximum TTL (currently 8 hours) and may be replaced on a successful reconnect; there is no special 30-day exception.

## 16. Packaging / release acceptance

Before release-related merge:

- build the actual Linux x86_64 Release Bundle;
- verify signed canonical manifest with the expected publisher public key or a disposable test key for test-only builds;
- run negative tamper tests;
- verify artifact version/platform/architecture/name/size/SHA context binding;
- clean install;
- update from previous known-good;
- failed provisioning/update keeps previous known-good usable;
- no private publisher key is committed or copied into runtime data.

## 17. Final report format

Produce a compact table with at least:

```text
Area | Result | Evidence | Notes
```

Results are only:

```text
PASS
FAIL
NOT TESTED
NOT APPLICABLE
```

Then include:

```text
SonicForge commit SHA
ControlDeck commit SHA(s)
PR numbers
real ASR/TTS models tested
GPU/backend
voice latency measurements
meeting duration tested
crash-recovery result
known remaining limitations
merge recommendation: YES / NO
```

Never turn NOT TESTED into PASS.

## 18. Merge execution for `SF受入マージ`

Only after the final report says `merge recommendation: YES`:

1. confirm no new commits landed since the tested SHAs;
2. if heads changed, re-run the affected gate before merge;
3. run the single batched milestone CI where configured;
4. inspect CI result and required checks;
5. inspect PR conflicts and unresolved review conversations;
6. merge generic ControlDeck dependency PRs first;
7. update/rebase dependent SonicForge branch if required;
8. run a short local smoke test against the exact rebased/updated SonicForge head;
9. merge SonicForge;
10. run post-merge smoke tests from `main`;
11. update `docs/implementation-status.md` with actual evidence and merge SHAs.

If any step fails, stop merging, fix the problem on a branch, and repeat the affected acceptance gate.

Do not use force merge, bypass required checks, or merge with known local functional failures.
