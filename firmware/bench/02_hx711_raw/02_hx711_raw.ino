// User's ESP32-S3-N16R8 board: HX711 DT -> GPIO4, SCK -> GPIO5.
// HX711 power/logic must be compatible with 3.3 V. No servos connected.
// Install "HX711 Arduino Library" by Bogdan Necula (bogde).
#include <HX711.h>

constexpr int HX711_DT = 4;
constexpr int HX711_SCK = 5;
HX711 scale;

void setup() {
  Serial.begin(115200);
  delay(1000);
  scale.begin(HX711_DT, HX711_SCK);
  Serial.println("HX711 RAW TEST - values are NOT grams");
}

void loop() {
  if (scale.wait_ready_timeout(1000)) {
    const long raw = scale.read();
    Serial.print("raw=");
    Serial.println(raw);
  } else {
    Serial.println("HX711 NOT READY - check power, DT and SCK wiring");
  }
  delay(250);
}
