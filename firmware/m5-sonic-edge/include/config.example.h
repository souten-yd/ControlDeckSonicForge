#pragma once

// Copy this file to include/config.h and fill only the values you need.
// include/config.h is intentionally ignored by git.

#define SONIC_WIFI_SSID ""
#define SONIC_WIFI_PASSWORD ""

// Direct trusted-LAN SonicForge mode. No user-facing auth is required.
#define SONIC_DIRECT_HOST "192.168.1.10"
#define SONIC_DIRECT_PORT 9140
#define SONIC_DIRECT_PATH "/addon/v1/live/ws"

// Set to 1 when this device should use ControlDeck's paired Device Relay.
// The relay is required for m5-voice-agent when the pipeline uses ControlDeck LLM.
// Basic ASR/dictation can stay direct/local with this set to 0.
#define SONIC_USE_CONTROLDECK_RELAY 0
#define SONIC_CONTROLDECK_HOST "192.168.1.10"
#define SONIC_CONTROLDECK_PORT 8765
#define SONIC_CONTROLDECK_RELAY_PATH "/api/v1/addon-runtime/sonic-forge/devices/relay/voice"

// First pairing only. Put the one-time code here, flash/connect once, then clear
// it. The firmware stores the rolling device token in ESP32 NVS Preferences.
// The code is never forwarded to SonicForge.
#define SONIC_PAIRING_CODE ""

// Presets:
//   m5-dictation   : mic -> ASR -> text (works direct/local)
//   m5-voice-agent : mic -> ASR -> ControlDeck LLM -> TTS (use relay)
#define SONIC_PRESET "m5-dictation"
#define SONIC_SOURCE_LANGUAGE "ja"
#define SONIC_TARGET_LANGUAGE "ja"
#define SONIC_TTS_VOICE_ID ""
#define SONIC_SYSTEM_PROMPT "日本語で簡潔に自然な音声会話として答えてください。"

#define SONIC_SPEAKER_VOLUME 96
#define SONIC_WIFI_CONNECT_TIMEOUT_MS 20000
#define SONIC_WS_RECONNECT_MS 2000
