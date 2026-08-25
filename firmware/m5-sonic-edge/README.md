# M5 Sonic Edge — CoreS3 baseline

This is the thin-device reference client for `sonic-edge/1`.

The firmware intentionally does **not** run ASR/LLM/TTS models locally. It owns microphone capture, PTT UI, WebSocket framing, state display and speaker playback. SonicForge/ControlDeck own the heavy pipeline.

## Supported baseline

- M5Stack CoreS3 via PlatformIO board `m5stack-cores3`
- 16 kHz / signed 16-bit / mono microphone uplink
- 20 ms frames (`320 samples`, `640 bytes`)
- `sonic-edge/1` binary frame encoding
- 24 kHz mono speaker downlink by negotiation
- half-duplex PTT
- WebSocket reconnect + heartbeat
- direct trusted-LAN mode without user-facing authentication
- optional ControlDeck Device Relay for pipelines that use the ControlDeck LLM
- ControlDeck device token saved in ESP32 NVS and refreshed on reconnect

CoreS3/M5Unified uses the microphone and speaker as mutually switched resources in the official microphone example. The baseline follows the same rule: microphone during PTT, speaker during response playback.

## Build

```bash
cd firmware/m5-sonic-edge
cp include/config.example.h include/config.h
# edit include/config.h
pio run
pio run --target upload
pio device monitor
```

`include/config.h` must not be committed.

## Direct local mode

Use this for ASR/dictation or other pipelines that do not need a ControlDeck Host capability:

```cpp
#define SONIC_USE_CONTROLDECK_RELAY 0
#define SONIC_DIRECT_HOST "192.168.68.57"
#define SONIC_PRESET "m5-dictation"
```

SonicForge must be bound to the trusted LAN/Tailscale interface or `0.0.0.0` and use its default `trusted-network` local access policy.

## Voice-agent / simultaneous-translation mode

A pipeline containing `host.ai.text` needs a ControlDeck execution identity. Use the generic ControlDeck Device Relay:

1. Enable/grant SonicForge `devices.relay` in ControlDeck.
2. From the SonicForge/ControlDeck UI create a pairing for relay `voice`.
3. Put the one-time pairing code in `SONIC_PAIRING_CODE` and flash/connect once.
4. The first relay connection returns a scoped device credential. Firmware stores it in NVS.
5. Clear `SONIC_PAIRING_CODE` from your local config after pairing. Subsequent boots reconnect with the stored credential and receive a refreshed credential automatically.

For normal voice chat:

```cpp
#define SONIC_USE_CONTROLDECK_RELAY 1
#define SONIC_PRESET "m5-voice-agent"
```

For streaming interpretation:

```cpp
#define SONIC_USE_CONTROLDECK_RELAY 1
#define SONIC_PRESET "simultaneous-translation"
#define SONIC_SOURCE_LANGUAGE "ja"
#define SONIC_TARGET_LANGUAGE "en"
```

The right virtual button (`PAIR RESET`) clears the NVS device token if re-pairing is required.

## Touch controls

The firmware maps the lower touchscreen edge to M5Unified virtual buttons:

- left / BtnA: hold to talk
- middle / BtnB: reconnect
- right / BtnC hold: clear pairing credential and restart

## Acceptance

Do not promote the firmware based on compilation alone. `SF受入確認` requires real CoreS3 validation of:

- microphone actually producing ~16 kHz frames without the slow-ADC problem seen on older analog M5 paths;
- no frame sequence drift/drop under Wi-Fi;
- first/second voice-turn latency;
- speaker underrun/noise;
- reconnect after Wi-Fi loss and ControlDeck/SonicForge restart;
- direct unauthenticated trusted-LAN dictation;
- paired relay voice-agent;
- SonicForge crash cleanup and clean reconnect;
- two or more turns without avoidable ASR/TTS/LLM cold reload.

Wake/VAD and AEC/barge-in are capability upgrades after this PTT baseline is measured. They are not required to prove the initial CoreS3 path.
