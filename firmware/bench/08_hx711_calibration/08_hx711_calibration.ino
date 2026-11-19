// ESP32-S3: HX711 DT=GPIO4, SCK=GPIO5, compatible 3.3 V module supply.
// Library: HX711 Arduino Library by bogde / Bogdan Necula.
// Commands with newline: T, C <known grams>. No servos required.
// Preferences keys match firmware/esp32/hub_node/hub_node.ino.
#include <HX711.h>
#include <Preferences.h>
#include <math.h>

HX711 scale;
Preferences prefs;
long zeroRaw = 0;
float factor = 0;
bool tared = false;
String input;
unsigned long lastPrint = 0;

bool averageRaw(long &result) {
  double sum = 0;
  for (int i = 0; i < 20; ++i) {
    if (!scale.wait_ready_timeout(1000)) return false;
    sum += scale.read();
  }
  result = long(sum / 20.0);
  return true;
}

void command(String text) {
  text.trim();
  if (text != "T" && !text.startsWith("C ")) {
    Serial.println("Use T with empty tray, or C <known grams> with reference mass");
    return;
  }
  long raw;
  Serial.println("Measuring: keep tray still...");
  if (!averageRaw(raw)) {
    Serial.println("ERROR: HX711 not ready; no calibration saved");
    return;
  }
  if (text == "T") {
    zeroRaw = raw;
    tared = true;
    prefs.putLong("zero", zeroRaw);
    prefs.putBool("tared", true);
    Serial.printf("TARE_SAVED | zero_raw=%ld\n", zeroRaw);
  } else {
    float grams = text.substring(2).toFloat();
    float difference = float(raw) - zeroRaw;
    if (!tared || !isfinite(grams) || grams <= 0 || fabs(difference) < 100) {
      Serial.println("ERROR: tare first; use positive known mass and check load response");
      return;
    }
    factor = difference / grams;
    prefs.putFloat("factor", factor);
    Serial.printf("CALIBRATION_SAVED | counts_per_g=%.6f\n", factor);
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  scale.begin(4, 5);
  prefs.begin("hubbench", false);
  zeroRaw = prefs.getLong("zero", 0);
  factor = prefs.getFloat("factor", 0);
  tared = prefs.getBool("tared", false);
  Serial.println("HX711 CALIBRATION | select Newline | T then C <known grams>");
  Serial.printf("Loaded zero=%ld, factor=%.6f\n", zeroRaw, factor);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (input.length()) command(input);
      input = "";
    } else if (input.length() < 40) input += c;
  }
  if (millis() - lastPrint < 500) return;
  lastPrint = millis();
  if (!scale.wait_ready_timeout(1000)) {
    Serial.println("HX711 NOT READY");
    return;
  }
  long raw = scale.read();
  Serial.printf("raw=%ld", raw);
  if (tared && isfinite(factor) && fabs(factor) > 0.001f) {
    Serial.printf(" | weight_g=%.2f\n", (float(raw) - zeroRaw) / factor);
  } else Serial.println(" | NOT CALIBRATED");
}
