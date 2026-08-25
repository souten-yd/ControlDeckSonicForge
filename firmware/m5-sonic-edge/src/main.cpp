#include <Arduino.h>
#include <ArduinoJson.h>
#include <M5Unified.h>
#include <Preferences.h>
#include <WebSocketsClient.h>
#include <WiFi.h>

#if __has_include("config.h")
#include "config.h"
#else
#include "config.example.h"
#endif

namespace {

constexpr uint32_t kMicRate = 16000;
constexpr size_t kMicSamples = 320;  // 20 ms @ 16 kHz
constexpr size_t kMicBytes = kMicSamples * sizeof(int16_t);
constexpr size_t kHeaderBytes = 18;
constexpr size_t kMaxAudioPayload = 8192;
constexpr uint8_t kStreamMic = 1;
constexpr uint8_t kStreamSpeaker = 2;
constexpr uint8_t kProtocolVersion = 1;
constexpr char kMagic[] = "SFA1";
constexpr char kPrefsNamespace[] = "sonic-edge";
constexpr char kTokenKey[] = "device-token";

WebSocketsClient ws;
Preferences prefs;
String deviceToken;
String extraHeaders;
bool wsConnected = false;
bool sonicReady = false;
bool helloSent = false;
bool recording = false;
bool speakerMode = false;
uint32_t micSequence = 0;
uint32_t micSampleClock = 0;
uint32_t outputRate = 24000;
int16_t micBuffer[kMicSamples];
int16_t speakerBuffer[kMaxAudioPayload / 2];
uint8_t txFrame[kHeaderBytes + kMicBytes];

String lastTranscript;
String lastResponse;

enum class UiState {
  Disconnected,
  Connecting,
  Idle,
  Listening,
  Transcribing,
  Thinking,
  Speaking,
  Error,
};

UiState uiState = UiState::Disconnected;

const char* stateLabel(UiState state) {
  switch (state) {
    case UiState::Disconnected: return "DISCONNECTED";
    case UiState::Connecting: return "CONNECTING";
    case UiState::Idle: return "IDLE";
    case UiState::Listening: return "LISTENING";
    case UiState::Transcribing: return "TRANSCRIBING";
    case UiState::Thinking: return "THINKING";
    case UiState::Speaking: return "SPEAKING";
    case UiState::Error: return "ERROR";
  }
  return "UNKNOWN";
}

void drawUi() {
  M5.Display.startWrite();
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.setTextSize(2);
  M5.Display.setCursor(8, 8);
  M5.Display.printf("SonicForge\n%s\n", stateLabel(uiState));

  M5.Display.setTextSize(1);
  M5.Display.printf("WiFi: %s\n", WiFi.isConnected() ? "OK" : "DOWN");
  M5.Display.printf("WS: %s  Mode: %s\n",
                   wsConnected ? "OK" : "DOWN",
                   SONIC_USE_CONTROLDECK_RELAY ? "ControlDeck" : "Direct");
  M5.Display.printf("Preset: %s\n", SONIC_PRESET);

  if (lastTranscript.length()) {
    M5.Display.setTextColor(TFT_CYAN, TFT_BLACK);
    M5.Display.printf("You: %.80s\n", lastTranscript.c_str());
  }
  if (lastResponse.length()) {
    M5.Display.setTextColor(TFT_GREEN, TFT_BLACK);
    M5.Display.printf("AI: %.80s\n", lastResponse.c_str());
  }

  const int h = 58;
  const int y = M5.Display.height() - h;
  const int w = M5.Display.width() / 3;
  M5.Display.fillRect(0, y, w - 2, h, recording ? TFT_RED : TFT_DARKGREEN);
  M5.Display.fillRect(w, y, w - 2, h, TFT_DARKGREY);
  M5.Display.fillRect(w * 2, y, M5.Display.width() - w * 2, h, TFT_MAROON);
  M5.Display.setTextColor(TFT_WHITE);
  M5.Display.setTextSize(1);
  M5.Display.setCursor(6, y + 20);
  M5.Display.print("HOLD TALK");
  M5.Display.setCursor(w + 8, y + 20);
  M5.Display.print("RECONNECT");
  M5.Display.setCursor(w * 2 + 8, y + 20);
  M5.Display.print("PAIR RESET");
  M5.Display.endWrite();
}

void setState(UiState state) {
  if (uiState == state) return;
  uiState = state;
  drawUi();
}

void putBe16(uint8_t* target, uint16_t value) {
  target[0] = static_cast<uint8_t>((value >> 8) & 0xff);
  target[1] = static_cast<uint8_t>(value & 0xff);
}

void putBe32(uint8_t* target, uint32_t value) {
  target[0] = static_cast<uint8_t>((value >> 24) & 0xff);
  target[1] = static_cast<uint8_t>((value >> 16) & 0xff);
  target[2] = static_cast<uint8_t>((value >> 8) & 0xff);
  target[3] = static_cast<uint8_t>(value & 0xff);
}

uint16_t readBe16(const uint8_t* source) {
  return (static_cast<uint16_t>(source[0]) << 8) |
         static_cast<uint16_t>(source[1]);
}

uint32_t readBe32(const uint8_t* source) {
  return (static_cast<uint32_t>(source[0]) << 24) |
         (static_cast<uint32_t>(source[1]) << 16) |
         (static_cast<uint32_t>(source[2]) << 8) |
         static_cast<uint32_t>(source[3]);
}

void enterMicMode() {
  if (!speakerMode && M5.Mic.isEnabled()) return;
  while (M5.Speaker.isPlaying()) {
    M5.delay(1);
  }
  M5.Speaker.end();
  M5.Mic.begin();
  speakerMode = false;
}

void enterSpeakerMode() {
  if (speakerMode && M5.Speaker.isEnabled()) return;
  while (M5.Mic.isRecording()) {
    M5.delay(1);
  }
  M5.Mic.end();
  M5.Speaker.begin();
  M5.Speaker.setVolume(SONIC_SPEAKER_VOLUME);
  speakerMode = true;
}

void saveDeviceToken(const char* token) {
  if (token == nullptr || token[0] == '\0') return;
  deviceToken = token;
  prefs.putString(kTokenKey, deviceToken);
  Serial.println("[sonic] Stored refreshed ControlDeck device token");
}

void clearDeviceToken() {
  prefs.remove(kTokenKey);
  deviceToken = "";
  Serial.println("[sonic] Device token cleared; pairing is required for relay mode");
}

void configureWsHeaders() {
  extraHeaders = "";
  if (!SONIC_USE_CONTROLDECK_RELAY) {
    ws.setExtraHeaders(nullptr);
    return;
  }
  if (deviceToken.length()) {
    extraHeaders = "Authorization: Bearer " + deviceToken + "\r\n";
  } else if (strlen(SONIC_PAIRING_CODE)) {
    extraHeaders = String("X-Control-Deck-Pairing-Code: ") + SONIC_PAIRING_CODE + "\r\n";
  }
  ws.setExtraHeaders(extraHeaders.length() ? extraHeaders.c_str() : nullptr);
}

void appendAudioFormat(JsonArray formats, uint32_t rate) {
  JsonObject value = formats.add<JsonObject>();
  value["codec"] = "pcm_s16le";
  value["rate"] = rate;
  value["channels"] = 1;
  value["frame_ms"] = 20;
}

void appendStage(JsonArray stages,
                 const char* id,
                 const char* kind,
                 const char* language) {
  JsonObject stage = stages.add<JsonObject>();
  stage["id"] = id;
  stage["kind"] = kind;
  stage["language"] = language;
  stage["quality"] = "balanced";
}

void sendHello() {
  if (!wsConnected || helloSent) return;

  JsonDocument doc;
  doc["type"] = "hello";
  JsonObject session = doc["session"].to<JsonObject>();
  session["preset"] = SONIC_PRESET;
  session["transport"] = "websocket";
  session["save_transcript"] = false;
  session["save_input_audio"] = false;
  session["save_output_audio"] = false;
  session["keep_warm"] = true;
  session["streaming_response"] = true;

  if (strcmp(SONIC_PRESET, "simultaneous-translation") == 0) {
    session["target_language"] = SONIC_TARGET_LANGUAGE;
  }

  JsonObject pipeline = session["pipeline"].to<JsonObject>();
  JsonObject input = pipeline["input"].to<JsonObject>();
  input["kind"] = "audio_stream";
  input["stream_id"] = "m5-mic";
  JsonArray stages = pipeline["stages"].to<JsonArray>();
  appendStage(stages, "asr", "speech.asr", SONIC_SOURCE_LANGUAGE);

  const bool needsLlm =
      strcmp(SONIC_PRESET, "m5-voice-agent") == 0 ||
      strcmp(SONIC_PRESET, "voice-assistant") == 0 ||
      strcmp(SONIC_PRESET, "simultaneous-translation") == 0;
  if (needsLlm) {
    JsonObject ai = stages.add<JsonObject>();
    ai["id"] = "assistant";
    ai["kind"] = "host.ai.text";
    ai["language"] = "auto";
    ai["quality"] = "balanced";
    JsonObject parameters = ai["parameters"].to<JsonObject>();
    parameters["system_prompt"] = SONIC_SYSTEM_PROMPT;
    parameters["max_tokens"] = 384;

    JsonObject tts = stages.add<JsonObject>();
    tts["id"] = "tts";
    tts["kind"] = "speech.tts";
    tts["language"] = SONIC_TARGET_LANGUAGE;
    tts["quality"] = "balanced";
    if (strlen(SONIC_TTS_VOICE_ID)) {
      tts["voice_id"] = SONIC_TTS_VOICE_ID;
    }
  }

  JsonObject delivery = pipeline["delivery"].to<JsonObject>();
  delivery["mode"] = "websocket";
  delivery["profile"] = "m5-live";

  JsonObject device = session["device"].to<JsonObject>();
  device["protocol"] = "sonic-edge/1";
  device["device_class"] = "m5";
  device["model"] = "core-s3";
  device["firmware"] = "0.1.0";
  device["psram_bytes"] = ESP.getPsramSize();
  JsonObject audio = device["audio"].to<JsonObject>();
  appendAudioFormat(audio["input"].to<JsonArray>(), kMicRate);
  appendAudioFormat(audio["output"].to<JsonArray>(), 24000);
  audio["aec"] = false;
  audio["vad"] = false;
  audio["wake"] = false;
  JsonObject ui = device["ui"].to<JsonObject>();
  ui["display"] = true;
  ui["touch"] = true;
  ui["buttons"] = 3;

  String payload;
  serializeJson(doc, payload);
  ws.sendTXT(payload);
  helloSent = true;
  Serial.printf("[sonic] hello: %s\n", payload.c_str());
}

void sendControl(const char* type) {
  if (!wsConnected || !sonicReady) return;
  JsonDocument doc;
  doc["type"] = type;
  String payload;
  serializeJson(doc, payload);
  ws.sendTXT(payload);
}

bool decodeSpeakerFrame(const uint8_t* data,
                        size_t length,
                        const int16_t*& samples,
                        size_t& sampleCount) {
  if (length < kHeaderBytes || memcmp(data, kMagic, 4) != 0) return false;
  if (data[4] != kProtocolVersion || data[5] != kStreamSpeaker || data[7] != 0) {
    return false;
  }
  const uint16_t payloadBytes = readBe16(data + 16);
  if (payloadBytes == 0 || payloadBytes > kMaxAudioPayload ||
      length != kHeaderBytes + payloadBytes || (payloadBytes & 1)) {
    return false;
  }
  // sequence/sample clock are decoded for diagnostics and future gap handling.
  const uint32_t sequence = readBe32(data + 8);
  const uint32_t sampleClock = readBe32(data + 12);
  (void)sequence;
  (void)sampleClock;
  memcpy(speakerBuffer, data + kHeaderBytes, payloadBytes);
  samples = speakerBuffer;
  sampleCount = payloadBytes / sizeof(int16_t);
  return true;
}

void playSpeakerFrame(const uint8_t* data, size_t length) {
  const int16_t* samples = nullptr;
  size_t sampleCount = 0;
  if (!decodeSpeakerFrame(data, length, samples, sampleCount)) {
    Serial.println("[sonic] invalid speaker frame");
    return;
  }
  enterSpeakerMode();
  // M5Unified playRaw consumes caller-owned runtime data asynchronously. Wait
  // for the previous 20 ms frame before reusing our persistent buffer.
  while (M5.Speaker.isPlaying()) {
    M5.delay(1);
  }
  M5.Speaker.playRaw(
      samples, sampleCount, outputRate, false, 1, 0, false);
}

void sendMicFrame() {
  if (!recording || !wsConnected || !sonicReady) return;
  if (!M5.Mic.record(micBuffer, kMicSamples, kMicRate, false)) return;

  memcpy(txFrame, kMagic, 4);
  txFrame[4] = kProtocolVersion;
  txFrame[5] = kStreamMic;
  txFrame[6] = 0;  // flags
  txFrame[7] = 0;  // reserved
  putBe32(txFrame + 8, micSequence);
  putBe32(txFrame + 12, micSampleClock);
  putBe16(txFrame + 16, static_cast<uint16_t>(kMicBytes));
  memcpy(txFrame + kHeaderBytes, micBuffer, kMicBytes);
  if (ws.sendBIN(txFrame, sizeof(txFrame))) {
    ++micSequence;
    micSampleClock += kMicSamples;
  }
}

void startPtt() {
  if (!sonicReady || recording || uiState == UiState::Speaking) return;
  enterMicMode();
  micSequence = 0;
  micSampleClock = 0;
  recording = true;
  sendControl("ptt.start");
  setState(UiState::Listening);
}

void stopPtt() {
  if (!recording) return;
  recording = false;
  sendControl("ptt.stop");
  setState(UiState::Transcribing);
}

void handleText(const uint8_t* payload, size_t length) {
  JsonDocument doc;
  const DeserializationError error = deserializeJson(doc, payload, length);
  if (error) {
    Serial.printf("[sonic] JSON error: %s\n", error.c_str());
    return;
  }
  const char* type = doc["type"] | "";

  if (strcmp(type, "control-deck.device.session") == 0) {
    const char* refreshed = doc["device_token"] | "";
    saveDeviceToken(refreshed);
    configureWsHeaders();
    sendHello();
    return;
  }
  if (strcmp(type, "ready") == 0) {
    outputRate = doc["output_format"]["rate"] | 24000;
    sonicReady = true;
    enterMicMode();
    setState(UiState::Idle);
    return;
  }
  if (strcmp(type, "ptt.started") == 0) {
    setState(UiState::Listening);
    return;
  }
  if (strcmp(type, "turn.started") == 0 ||
      strcmp(type, "stage.started") == 0) {
    if (!recording) setState(UiState::Transcribing);
    return;
  }
  if (strcmp(type, "turn.transcript") == 0) {
    lastTranscript = static_cast<const char*>(doc["text"] | "");
    setState(UiState::Thinking);
    drawUi();
    return;
  }
  if (strcmp(type, "turn.response_text.delta") == 0) {
    lastResponse += static_cast<const char*>(doc["text"] | "");
    if (lastResponse.length() > 400) {
      lastResponse.remove(0, lastResponse.length() - 400);
    }
    setState(UiState::Thinking);
    return;
  }
  if (strcmp(type, "turn.response_text") == 0) {
    lastResponse = static_cast<const char*>(doc["text"] | "");
    drawUi();
    return;
  }
  if (strcmp(type, "turn.audio.start") == 0) {
    outputRate = doc["format"]["rate"] | outputRate;
    enterSpeakerMode();
    setState(UiState::Speaking);
    return;
  }
  if (strcmp(type, "turn.complete") == 0) {
    recording = false;
    while (M5.Speaker.isPlaying()) {
      M5.delay(1);
    }
    enterMicMode();
    setState(UiState::Idle);
    return;
  }
  if (strcmp(type, "turn.error") == 0 || strcmp(type, "error") == 0) {
    recording = false;
    Serial.printf("[sonic] server error: %s\n",
                  static_cast<const char*>(doc["message"] | "unknown"));
    enterMicMode();
    setState(UiState::Error);
    return;
  }
}

void onWsEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      wsConnected = true;
      sonicReady = false;
      helloSent = false;
      lastResponse = "";
      setState(UiState::Connecting);
      if (!SONIC_USE_CONTROLDECK_RELAY) {
        sendHello();
      }
      break;
    case WStype_TEXT:
      handleText(payload, length);
      break;
    case WStype_BIN:
      playSpeakerFrame(payload, length);
      break;
    case WStype_DISCONNECTED:
      wsConnected = false;
      sonicReady = false;
      helloSent = false;
      recording = false;
      enterMicMode();
      setState(UiState::Disconnected);
      break;
    case WStype_ERROR:
      setState(UiState::Error);
      break;
    default:
      break;
  }
}

void connectWifi() {
  if (WiFi.isConnected()) return;
  setState(UiState::Connecting);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(SONIC_WIFI_SSID, SONIC_WIFI_PASSWORD);
  const uint32_t started = millis();
  while (!WiFi.isConnected() && millis() - started < SONIC_WIFI_CONNECT_TIMEOUT_MS) {
    M5.update();
    M5.delay(100);
  }
  Serial.printf("[sonic] WiFi: %s IP=%s\n",
                WiFi.isConnected() ? "connected" : "failed",
                WiFi.localIP().toString().c_str());
}

void beginWebSocket() {
  configureWsHeaders();
  if (SONIC_USE_CONTROLDECK_RELAY) {
    ws.begin(SONIC_CONTROLDECK_HOST,
             SONIC_CONTROLDECK_PORT,
             SONIC_CONTROLDECK_RELAY_PATH);
  } else {
    ws.begin(SONIC_DIRECT_HOST, SONIC_DIRECT_PORT, SONIC_DIRECT_PATH);
  }
  ws.onEvent(onWsEvent);
  ws.setReconnectInterval(SONIC_WS_RECONNECT_MS);
  ws.enableHeartbeat(15000, 3000, 2);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  auto cfg = M5.config();
  M5.begin(cfg);
  M5.setTouchButtonHeight(64);
  M5.Display.setBrightness(128);
  M5.Display.setRotation(1);

  prefs.begin(kPrefsNamespace, false);
  deviceToken = prefs.getString(kTokenKey, "");

  M5.Speaker.setVolume(SONIC_SPEAKER_VOLUME);
  M5.Speaker.end();
  M5.Mic.begin();
  drawUi();

  connectWifi();
  beginWebSocket();
}

void loop() {
  M5.update();
  if (!WiFi.isConnected()) {
    connectWifi();
  }
  ws.loop();

  if (M5.BtnA.wasPressed()) {
    startPtt();
  }
  if (recording) {
    sendMicFrame();
  }
  if (M5.BtnA.wasReleased()) {
    stopPtt();
  }
  if (M5.BtnB.wasClicked()) {
    ws.disconnect();
    configureWsHeaders();
    setState(UiState::Connecting);
  }
  if (M5.BtnC.wasHold()) {
    clearDeviceToken();
    ws.disconnect();
    M5.delay(250);
    ESP.restart();
  }

  M5.delay(1);
}
