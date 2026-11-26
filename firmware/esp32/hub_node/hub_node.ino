// ESP32-S3-N16R8, bench-only complete node. See README_TH.md before powering.
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <HX711.h>
#include <ESP32Servo.h>
#include "secrets.h"

constexpr int HX_DT = 4, HX_SCK = 5, GATE_PIN = 6, CHUTE_PIN = 7;
// D024: height sensor is HY-SRF05 ultrasonic (replaces VL53L0X). VCC = Adapter +5V.
// TRIG = GPIO12 (3.3 V output is enough). ECHO is 5 V: ECHO--10k--GPIO13--15k--GND.
// Never connect ECHO directly to GPIO13. SRF05 OUT pin is not used.
constexpr int US_TRIG = 12, US_ECHO = 13;
constexpr uint32_t US_TIMEOUT_US = 30000;          // ~5 m round trip; no echo -> invalid
constexpr float US_MIN_MM = 20, US_MAX_MM = 4000;  // SRF05 usable range
constexpr int BUTTON_PIN = 10;
// D011: one E18 at the tray (GPIO11, R v2 divider). GPIO14 unused.
constexpr int IR_COUNT = 1;
constexpr int IR_PINS[IR_COUNT] = { 11 };
const char *IR_NAMES[IR_COUNT] = { "tray" };
// E18 v2 interface per channel: +5V--1k--OUT--10k--GPIO--15k--GND.
// External resistors set both logic levels; do not enable internal pull-ups.
constexpr int LED_GREEN = 15, LED_YELLOW = 16, LED_RED = 17;
// Nominal bench positions, NOT calibrated physical chute angles.
// MG90S on 1000-2000 us: write(0..180) ~ 90 deg physical, so 180 -> 0 swings the gate ~90 deg.
constexpr int GATE_CLOSED = 180, GATE_OPEN = 0;
constexpr int CHUTE_ANGLES[] = { 60, 90, 120 };
constexpr float STABILITY_G = 5.0f;
constexpr int WINDOW = 10;

WiFiClient network;
PubSubClient mqtt(network);
Preferences prefs;
HX711 scale;
Servo gateServo, chuteServo;
// Gate moves gradually at about half the MG90S native speed: 6 command-degrees every 10 ms
// (180 -> 0 in ~0.3 s). Non-blocking: moveGate() sets the target, updateGate() steps in loop().
constexpr int GATE_STEP_DEG = 6;
constexpr uint32_t GATE_STEP_MS = 10;
int gatePos = 0, gateTarget = 0;
uint32_t lastGateStep = 0;
void moveGate(int angle) { gateTarget = constrain(angle, 0, 180); }
void updateGate() {
  if (gatePos == gateTarget || millis() - lastGateStep < GATE_STEP_MS) return;
  lastGateStep = millis();
  const int delta = gateTarget - gatePos;
  gatePos += constrain(delta, -GATE_STEP_DEG, GATE_STEP_DEG);
  gateServo.write(gatePos);
}
// "tof*" names kept for the existing MQTT/Serial contract; they now describe the SRF05.
// tofFound = an echo was received recently (sensor answering).
String sessionId, activeJob, targetBin, displayState = "PAUSED_OPERATOR";
bool released = false, nodeFault = false, tofFound = false, distanceValid = false, hxSeen = false;
long zeroRaw = 0;
float scaleFactor = 0, emptyDistance = 0, distanceMm = 0;
bool hasTare = false;
long samples[WINDOW];
int sampleCount = 0, sampleIndex = 0;
uint32_t lastUsPing = 0, lastEcho = 0;
uint32_t lastHx = 0, lastTof = 0, lastPublish = 0, lastConnect = 0, lastLease = 0, sequence = 0;
uint32_t gateDoneAt = 0;
String releaseCommand;
bool irReading[IR_COUNT] = {}, irStable[IR_COUNT] = {};
uint32_t irChangedAt[IR_COUNT] = {};
bool buttonReading = false, buttonStable = false;
uint32_t buttonChangedAt = 0;
String serialLine;

struct PassageEvent {
  uint32_t id, at;
  String job, sensor;
  bool afterRelease;
};
PassageEvent events[16];
uint32_t eventId = 0;
int eventCount = 0, eventNext = 0;
struct CachedAck {
  String id, json;
};
CachedAck ackCache[16];
int ackNext = 0;

bool elapsed(uint32_t now, uint32_t then, uint32_t ms) {
  return uint32_t(now - then) >= ms;
}

void envelope(JsonDocument &doc) {
  doc["schema_version"] = 1;
  doc["device_id"] = "node-01";
  doc["session_id"] = sessionId;
  doc["seq"] = sequence++;
  doc["uptime_ms"] = millis();
  if (activeJob.length()) doc["job_id"] = activeJob;
  else doc["job_id"] = nullptr;
}

void publishJson(const char *topic, JsonDocument &doc) {
  String payload;
  serializeJson(doc, payload);
  if (mqtt.connected()) mqtt.publish(topic, payload.c_str(), false);
}

void ack(const String &id, const char *status, const char *reason = "") {
  JsonDocument doc;
  envelope(doc);
  doc["command_id"] = id;
  doc["status"] = status;
  doc["reason"] = reason;
  String payload;
  serializeJson(doc, payload);
  mqtt.publish("sorter/ack", payload.c_str(), false);
  if (String(status) != "ACCEPTED") {
    ackCache[ackNext] = { id, payload };
    ackNext = (ackNext + 1) % 16;
  }
}

int binIndex(const String &name) {
  if (name == "A") return 0;
  if (name == "B") return 1;
  if (name == "HOLD") return 2;
  return -1;
}

bool pathClear() {
  for (int i = 0; i < IR_COUNT; i++)
    if (irStable[i]) return false;
  return true;
}

void latchFault() {
  nodeFault = true;
  // Never move a chute carrying a released parcel. Before release keep gate closed.
  if (!released) moveGate(GATE_CLOSED);
}

void onCommand(char *, byte *payload, unsigned int length) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, length)) return;
  if ((doc["schema_version"] | 0) != 1) return;
  String id = doc["command_id"] | "";
  String job = doc["job_id"] | "";
  String action = doc["action"] | "";
  if (!id.length()) return;
  if (String(doc["node_session_id"] | "") != sessionId) {
    ack(id, "REJECTED", "SESSION_MISMATCH");
    return;
  }
  uint32_t expiry = doc["expires_uptime_ms"] | 0UL;
  if (int32_t(expiry - millis()) <= 0 || int32_t(expiry - millis()) > 6000) {
    ack(id, "REJECTED", "EXPIRED_COMMAND");
    return;
  }
  if (action == "PING") {
    lastLease = millis();
    displayState = doc["display_state"] | "PAUSED_OPERATOR";
    return;
  }
  for (auto &cached : ackCache)
    if (cached.id == id) {
      mqtt.publish("sorter/ack", cached.json.c_str(), false);
      return;
    }
  if (id == releaseCommand && gateDoneAt) {
    ack(id, "ACCEPTED");
    return;
  }
  if (action == "FAULT") {
    latchFault();
    ack(id, "DONE");
    return;
  }
  if (elapsed(millis(), lastLease, 3000)) {
    ack(id, "REJECTED", "CONTROLLER_LEASE_EXPIRED");
    return;
  }
  if (action == "RESET") {
    if (!pathClear()) {
      ack(id, "REJECTED", "IR_PATH_BLOCKED");
      return;
    }
    moveGate(GATE_CLOSED);
    activeJob = "";
    targetBin = "";
    released = false;
    nodeFault = false;
    gateDoneAt = 0;
    releaseCommand = "";
    ack(id, "DONE");
    return;
  }
  if (nodeFault) {
    ack(id, "REJECTED", "NODE_FAULT");
    return;
  }
  if (action == "SERVO_TEST") {
    // Bench-only manual move from the web. Refused during any job or after release.
    const String servo = doc["servo"] | "";
    const int angle = doc["angle"] | -1;
    if (activeJob.length() || released || angle < 0 || angle > 180
        || (servo != "gate" && servo != "chute")) {
      ack(id, "REJECTED", "SERVO_TEST_NOT_ALLOWED");
      return;
    }
    if (servo == "gate") moveGate(angle); else chuteServo.write(angle);
    Serial.printf("SERVO_TEST %s=%d\n", servo.c_str(), angle);
    ack(id, "DONE");
    return;
  }
  if (action == "POSITION") {
    String bin = doc["target_bin"] | "";
    int index = binIndex(bin);
    if (!job.length() || index < 0 || released || activeJob.length()) {  // D011: parcel sits on the tray IR
      ack(id, "REJECTED", "POSITION_NOT_ALLOWED");
      return;
    }
    activeJob = job;
    targetBin = bin;
    moveGate(GATE_CLOSED);
    chuteServo.write(CHUTE_ANGLES[index]);
    // DONE = command applied, NOT proof of measured angle or bin arrival.
    ack(id, "DONE");
    return;
  }
  if (job != activeJob || !job.length()) {
    ack(id, "REJECTED", "JOB_MISMATCH");
    return;
  }
  if (action == "RELEASE") {
    if (released || String(doc["target_bin"] | "") != targetBin
        || !(doc["angle_verified"] | false)) {  // D011: parcel sits on the tray IR
      ack(id, "REJECTED", "RELEASE_NOT_ALLOWED");
      return;
    }
    released = true;
    releaseCommand = id;
    moveGate(GATE_OPEN);
    gateDoneAt = millis() + 500;
    if (gateDoneAt == 0) gateDoneAt = 1;
    ack(id, "ACCEPTED");
    return;
  }
  if (action == "COMPLETE") {
    if (!released || !pathClear()) {
      ack(id, "REJECTED", "COMPLETE_NOT_ALLOWED");
      return;
    }
    moveGate(GATE_CLOSED);
    activeJob = "";
    targetBin = "";
    released = false;
    ack(id, "DONE");
    return;
  }
  ack(id, "REJECTED", "UNKNOWN_ACTION");
}

float meanRaw() {
  double sum = 0;
  for (int i = 0; i < sampleCount; i++) sum += samples[i];
  return sampleCount ? float(sum / sampleCount) : 0;
}

bool weightValid() {
  return hxSeen && !elapsed(millis(), lastHx, 2000) && hasTare && fabs(scaleFactor) > 0.001f;
}

bool weightStable() {
  if (!weightValid() || sampleCount < WINDOW) return false;
  long lo = samples[0], hi = samples[0];
  for (int i = 1; i < sampleCount; i++) {
    lo = min(lo, samples[i]);
    hi = max(hi, samples[i]);
  }
  return fabs(float(hi - lo) / scaleFactor) <= STABILITY_G;
}

void sampleSensors() {
  uint32_t now = millis();
  if (scale.is_ready()) {
    samples[sampleIndex] = scale.read();
    sampleIndex = (sampleIndex + 1) % WINDOW;
    sampleCount = min(sampleCount + 1, WINDOW);
    lastHx = millis();
    hxSeen = true;
  }
  if (elapsed(now, lastUsPing, 300)) {
    lastUsPing = now;
    digitalWrite(US_TRIG, LOW);
    delayMicroseconds(2);
    digitalWrite(US_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(US_TRIG, LOW);
    // Blocks at most US_TIMEOUT_US (30 ms) every 300 ms.
    const unsigned long echoUs = pulseIn(US_ECHO, HIGH, US_TIMEOUT_US);
    const float mm = echoUs * 0.343f / 2.0f;  // speed of sound ~343 m/s at ~20 C
    distanceValid = echoUs > 0 && mm >= US_MIN_MM && mm <= US_MAX_MM;
    if (echoUs > 0) {
      tofFound = true;
      lastEcho = millis();
    } else if (elapsed(millis(), lastEcho, 3000)) {
      tofFound = false;
    }
    if (distanceValid) {
      distanceMm = mm;
      lastTof = millis();
    }
  }
  now = millis();
  for (int i = 0; i < IR_COUNT; i++) {
    bool reading = digitalRead(IR_PINS[i]) == LOW;
    if (reading != irReading[i]) {
      irReading[i] = reading;
      irChangedAt[i] = now;
    }
    if (reading != irStable[i] && elapsed(now, irChangedAt[i], 30)) {
      irStable[i] = reading;
      if (reading) {
        events[eventNext] = { ++eventId, now, activeJob, String(IR_NAMES[i]), released };
        eventNext = (eventNext + 1) % 16;
        eventCount = min(eventCount + 1, 16);
      }
    }
  }
  bool pressed = digitalRead(BUTTON_PIN) == LOW;
  if (pressed != buttonReading) {
    buttonReading = pressed;
    buttonChangedAt = now;
  }
  if (pressed != buttonStable && elapsed(now, buttonChangedAt, 40)) {
    buttonStable = pressed;
    if (pressed) {
      JsonDocument doc;
      envelope(doc);
      doc["event"] = "PAUSE_BUTTON";
      publishJson("sorter/status", doc);
    }
  }
}

void telemetry() {
  JsonDocument doc;
  envelope(doc);
  doc["raw"] = meanRaw();
  doc["valid"] = weightValid();
  doc["tare_ready"] = hasTare;
  doc["scale_factor"] = scaleFactor;
  doc["node_fault"] = nodeFault;
  doc["stable"] = weightStable();
  if (weightValid()) doc["weight_g"] = (meanRaw() - zeroRaw) / scaleFactor;
  else doc["weight_g"] = nullptr;
  publishJson("sorter/weight", doc);

  doc.clear();
  envelope(doc);
  bool valid = distanceValid && !elapsed(millis(), lastTof, 2000) && emptyDistance > 0;
  float height = emptyDistance - distanceMm;
  // A large negative height is invalid geometry, not a safe zero-height box.
  valid = valid && height >= -10;
  doc["valid"] = valid;
  doc["sensor_found"] = tofFound;
  doc["distance_valid"] = distanceValid;
  doc["empty_distance_mm"] = emptyDistance;
  if (distanceValid) doc["distance_mm"] = distanceMm;
  if (valid) doc["height_mm"] = max(0.0f, height);
  else doc["height_mm"] = nullptr;
  publishJson("sorter/height", doc);

  doc.clear();
  envelope(doc);
  JsonObject active = doc["active"].to<JsonObject>();
  for (int i = 0; i < IR_COUNT; i++) active[IR_NAMES[i]] = irStable[i];
  JsonArray log = doc["events"].to<JsonArray>();
  for (int n = 0; n < eventCount; n++) {
    int index = (eventNext - eventCount + n + 16) % 16;
    auto &event = events[index];
    JsonObject item = log.add<JsonObject>();
    item["id"] = event.id;
    item["uptime_ms"] = event.at;
    item["job_id"] = event.job;
    item["sensor"] = event.sensor;
    item["after_release"] = event.afterRelease;
  }
  publishJson("sorter/passage", doc);

  doc.clear();
  envelope(doc);
  doc["node_fault"] = nodeFault;
  doc["released"] = released;
  doc["target_bin"] = targetBin;
  doc["display_state"] = displayState;
  publishJson("sorter/actuator", doc);
}

void printHelp() {
  Serial.println("HUB NODE BENCH READY | Serial 115200, line ending = Newline");
  Serial.println("  S          = show all Node sensor values (read-only, works during a job)");
  Serial.println("  T          = HX711 tare: tray EMPTY, then send T");
  Serial.println("  C <grams>  = HX711 calibrate with a WEIGHED reference, e.g. C 100");
  Serial.println("  H          = SRF05 save empty-tray distance: tray EMPTY, then send H");
  Serial.println("  R          = reset SRF05 reading (clears valid flag)");
  Serial.println("  T/C/H/R are blocked while a job is active. Other text shows this help.");
}

// Read-only snapshot of Node sensors for bench diagnosis (Serial command S).
// Gateway sensors (AS5600/BH1750) live on the Pi and are not visible here.
void printStatus() {
  const uint32_t now = millis();
  Serial.println("---- STATUS ----");
  Serial.printf("NET   wifi=%s ip=%s mqtt=%s\n",
                WiFi.status() == WL_CONNECTED ? "OK" : "DOWN",
                WiFi.localIP().toString().c_str(), mqtt.connected() ? "OK" : "DOWN");
  Serial.printf("HX711 seen=%d fresh=%d samples=%d/%d raw=%.0f tared=%d factor=%.6f",
                hxSeen, hxSeen && !elapsed(now, lastHx, 2000), sampleCount, WINDOW,
                meanRaw(), hasTare, scaleFactor);
  if (weightValid()) Serial.printf(" weight_g=%.1f stable=%d\n",
                                   (meanRaw() - zeroRaw) / scaleFactor, weightStable());
  else Serial.println(" weight_g=NOT_CALIBRATED");
  Serial.printf("SRF05 echo=%d valid=%d fresh=%d distance_mm=%.0f empty_mm=%.0f",
                tofFound, distanceValid, !elapsed(now, lastTof, 2000), distanceMm, emptyDistance);
  if (distanceValid && emptyDistance > 0) Serial.printf(" height_mm=%.0f\n", emptyDistance - distanceMm);
  else Serial.println(" height_mm=N/A");
  for (int i = 0; i < IR_COUNT; i++)
    Serial.printf("IR    %s gpio%d=%s\n", IR_NAMES[i], IR_PINS[i], irStable[i] ? "DETECTED" : "CLEAR");
  Serial.printf("BTN   gpio%d=%s\n", BUTTON_PIN, buttonStable ? "PRESSED" : "RELEASED");
  Serial.printf("NODE  state=%s job=%s fault=%d released=%d\n", displayState.c_str(),
                activeJob.length() ? activeJob.c_str() : "-", nodeFault, released);
  Serial.println("----------------");
}

void serialCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') {
      if (serialLine.length() < 64) serialLine += c;
      continue;
    }
    serialLine.trim();
    if (activeJob.length() && serialLine != "S") {
      Serial.println("Calibration blocked: active job");
      serialLine = "";
      continue;
    }
    if (serialLine == "T" && sampleCount == WINDOW && hxSeen && !elapsed(millis(), lastHx, 2000)) {
      zeroRaw = long(meanRaw());
      hasTare = true;
      prefs.putLong("zero", zeroRaw);
      prefs.putBool("tared", true);
      Serial.printf("TARE_SAVED raw=%ld\n", zeroRaw);
    } else if (serialLine.startsWith("C ") && hasTare && sampleCount == WINDOW
               && hxSeen && !elapsed(millis(), lastHx, 2000)) {
      float grams = serialLine.substring(2).toFloat();
      float difference = meanRaw() - zeroRaw;
      if (grams > 0 && fabs(difference) > 100) {
        scaleFactor = difference / grams;
        prefs.putFloat("factor", scaleFactor);
        Serial.printf("SCALE_SAVED counts_per_g=%.6f\n", scaleFactor);
      } else Serial.println("Invalid mass/raw difference");
    } else if (serialLine == "H" && distanceValid && !elapsed(millis(), lastTof, 2000)) {
      emptyDistance = distanceMm;
      prefs.putFloat("empty", emptyDistance);
      Serial.printf("EMPTY_DISTANCE_SAVED mm=%.1f\n", emptyDistance);
    } else if (serialLine == "S") {
      printStatus();
    } else if (serialLine == "R") {
      distanceValid = false;
      lastUsPing = millis() - 300;  // ping again on the next loop
      Serial.println("SRF05 reading reset");
    } else if (serialLine == "T" || serialLine.startsWith("C ")) {
      Serial.printf("HX711 not ready: seen=%d samples=%d/%d fresh=%d tared=%d\n",
                    hxSeen, sampleCount, WINDOW, hxSeen && !elapsed(millis(), lastHx, 2000), hasTare);
    } else if (serialLine == "H") {
      Serial.printf("SRF05 not ready: echo=%d valid=%d fresh=%d\n",
                    tofFound, distanceValid, !elapsed(millis(), lastTof, 2000));
    } else {
      printHelp();
    }
    serialLine = "";
  }
}

void connectNetwork() {
  if (!elapsed(millis(), lastConnect, 2000)) return;
  lastConnect = millis();
  static int lastWifi = -1;
  const int wifi = WiFi.status();
  if (wifi != lastWifi) {  // Diagnostic: report Wi-Fi state changes only.
    lastWifi = wifi;
    if (wifi == WL_CONNECTED) Serial.printf("WIFI CONNECTED ip=%s\n", WiFi.localIP().toString().c_str());
    else Serial.printf("WIFI NOT CONNECTED status=%d (1=SSID not found, 4=failed, 6=disconnected)\n", wifi);
  }
  if (wifi != WL_CONNECTED) return;  // ESP32 WiFi auto-reconnect handles WiFi.
  if (!mqtt.connected()) {
    String clientId = "hub-node-" + sessionId;
    if (mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD)) {
      mqtt.subscribe("sorter/cmd", 1);
      Serial.println("MQTT CONNECTED");
    } else {
      Serial.printf("MQTT FAILED host=%s state=%d (-2=no TCP, 4=bad user/pass, 5=not authorized)\n",
                    MQTT_HOST, mqtt.state());
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(20);
  delay(1000);
  sessionId = String(esp_random(), HEX) + String(esp_random(), HEX);
  prefs.begin("hubbench", false);
  zeroRaw = prefs.getLong("zero", 0);
  scaleFactor = prefs.getFloat("factor", 0);
  hasTare = prefs.getBool("tared", false);
  emptyDistance = prefs.getFloat("empty", 0);
  scale.begin(HX_DT, HX_SCK);
  pinMode(US_TRIG, OUTPUT);
  digitalWrite(US_TRIG, LOW);
  pinMode(US_ECHO, INPUT);  // external 10k/15k divider sets the level; no internal pull
  for (int i = 0; i < IR_COUNT; i++) {
    pinMode(IR_PINS[i], INPUT);
    irReading[i] = irStable[i] = (digitalRead(IR_PINS[i]) == LOW);
  }
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  gateServo.setPeriodHertz(50);
  chuteServo.setPeriodHertz(50);
  gateServo.attach(GATE_PIN, 1000, 2000);
  // MG996R: 1000-2000 us gave only ~90 deg (05c test). 600-2400 us ~ 180 deg.
  // write(0..180) now maps to this wider range; CHUTE_ANGLES are command values, not calibrated.
  chuteServo.attach(CHUTE_PIN, 600, 2400);
  gatePos = gateTarget = GATE_CLOSED;
  gateServo.write(GATE_CLOSED);  // boot: go straight to closed
  chuteServo.write(90);
  if (!gateServo.attached() || !chuteServo.attached()) nodeFault = true;
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onCommand);
  mqtt.setBufferSize(8192);
  mqtt.setKeepAlive(5);
  mqtt.setSocketTimeout(1);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  printHelp();
}

void loop() {
  connectNetwork();
  mqtt.loop();
  if (activeJob.length() && (!mqtt.connected() || elapsed(millis(), lastLease, 4000))) latchFault();
  updateGate();
  sampleSensors();
  serialCommands();
  if (gateDoneAt && int32_t(millis() - gateDoneAt) >= 0) {
    gateDoneAt = 0;
    ack(releaseCommand, "DONE");
  }
  if (elapsed(millis(), lastPublish, 500)) {
    lastPublish = millis();
    telemetry();
  }
  bool faulty = nodeFault || displayState == "FAULT" || displayState == "PAUSED_AI";
  bool ready = !faulty && displayState == "IDLE" && mqtt.connected();
  digitalWrite(LED_GREEN, ready);
  digitalWrite(LED_RED, faulty);
  bool paused = displayState == "PAUSED_OPERATOR" || displayState == "BLOCKED" || !mqtt.connected();
  digitalWrite(LED_YELLOW, !faulty && !ready && (!paused || (millis() / 500) % 2));
  delay(2);
}
