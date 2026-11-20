// ESP32-S3-N16R8, bench-only complete node. See README_TH.md before powering.
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Preferences.h>
#include <HX711.h>
#include <Adafruit_VL53L0X.h>
#include <ESP32Servo.h>
#include "secrets.h"

constexpr int HX_DT = 4, HX_SCK = 5, GATE_PIN = 6, CHUTE_PIN = 7, SDA_PIN = 8, SCL_PIN = 9;
constexpr int BUTTON_PIN = 10;
// D011: one E18 at the tray (GPIO11, R v2 divider). GPIO12-14 are no longer used.
constexpr int IR_COUNT = 1;
constexpr int IR_PINS[IR_COUNT] = { 11 };
const char *IR_NAMES[IR_COUNT] = { "tray" };
// E18 v2 interface per channel: +5V--1k--OUT--10k--GPIO--15k--GND.
// External resistors set both logic levels; do not enable internal pull-ups.
constexpr int LED_GREEN = 15, LED_YELLOW = 16, LED_RED = 17;
// Nominal bench positions, NOT calibrated physical chute angles.
constexpr int GATE_CLOSED = 90, GATE_OPEN = 60;
constexpr int CHUTE_ANGLES[] = { 60, 90, 120 };
constexpr float STABILITY_G = 5.0f;
constexpr int WINDOW = 10;

WiFiClient network;
PubSubClient mqtt(network);
Preferences prefs;
HX711 scale;
Adafruit_VL53L0X tof;
Servo gateServo, chuteServo;
String sessionId, activeJob, targetBin, displayState = "PAUSED_OPERATOR";
bool released = false, nodeFault = false, tofFound = false, distanceValid = false, hxSeen = false;
long zeroRaw = 0;
float scaleFactor = 0, emptyDistance = 0, distanceMm = 0;
bool hasTare = false;
long samples[WINDOW];
int sampleCount = 0, sampleIndex = 0;
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
  if (!released) gateServo.write(GATE_CLOSED);
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
    gateServo.write(GATE_CLOSED);
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
    (servo == "gate" ? gateServo : chuteServo).write(angle);
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
    gateServo.write(GATE_CLOSED);
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
    gateServo.write(GATE_OPEN);
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
    gateServo.write(GATE_CLOSED);
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
  if (tofFound && elapsed(now, lastTof, 300)) {
    lastTof = now;
    VL53L0X_RangingMeasurementData_t measurement = {};
    auto result = tof.rangingTest(&measurement, false);
    distanceValid = result == VL53L0X_ERROR_NONE && measurement.RangeStatus == 0;
    if (distanceValid) distanceMm = measurement.RangeMilliMeter;
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

void serialCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') {
      if (serialLine.length() < 64) serialLine += c;
      continue;
    }
    serialLine.trim();
    if (activeJob.length()) {
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
    } else if (serialLine == "R") {
      tofFound = tof.begin(0x29, false, &Wire);
      distanceValid = false;
      Serial.println(tofFound ? "ToF initialized" : "ToF not found");
    } else if (serialLine == "T" || serialLine.startsWith("C ")) {
      Serial.printf("HX711 not ready: seen=%d samples=%d/%d fresh=%d tared=%d\n",
                    hxSeen, sampleCount, WINDOW, hxSeen && !elapsed(millis(), lastHx, 2000), hasTare);
    } else if (serialLine == "H") {
      Serial.printf("ToF not ready: found=%d valid=%d fresh=%d\n",
                    tofFound, distanceValid, !elapsed(millis(), lastTof, 2000));
    } else {
      Serial.println("Commands: T (empty tare), C <known grams>, H (empty ToF), R (retry ToF)");
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
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);
  tofFound = tof.begin(0x29, false, &Wire);
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
  chuteServo.attach(CHUTE_PIN, 1000, 2000);
  gateServo.write(GATE_CLOSED);
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
  Serial.println("HUB NODE BENCH READY | T / C <grams> / H / R (newline required)");
}

void loop() {
  connectNetwork();
  mqtt.loop();
  if (activeJob.length() && (!mqtt.connected() || elapsed(millis(), lastLease, 4000))) latchFault();
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
