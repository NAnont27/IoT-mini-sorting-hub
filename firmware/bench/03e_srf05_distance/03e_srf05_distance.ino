// ESP32-S3: HY-SRF05 ultrasonic distance test (D024, replaces VL53L0X).
// VCC = Adapter +5V, GND = common GND.
// TRIG -> GPIO12 directly (3.3 V output is enough).
// ECHO is 5 V: ECHO--10k--GPIO13--15k--GND. NEVER connect ECHO straight to GPIO13.
// OUT pin is not used. Power order: ESP32 USB first, then Adapter; off: Adapter first.
#include <Arduino.h>

constexpr int TRIG = 12, ECHO = 13;
constexpr uint32_t TIMEOUT_US = 30000;
constexpr uint32_t PERIOD_MS = 300;

void setup() {
  Serial.begin(115200);
  delay(1000);
  pinMode(TRIG, OUTPUT);
  digitalWrite(TRIG, LOW);
  pinMode(ECHO, INPUT);
  Serial.println("SRF05 TEST | TRIG=GPIO12, ECHO=GPIO13 via 10k/15k | every 300 ms");
}

void loop() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  const unsigned long echoUs = pulseIn(ECHO, HIGH, TIMEOUT_US);
  if (echoUs == 0) {
    Serial.println("NO_ECHO (check 5V, GND, divider, nothing in range?)");
  } else {
    const float mm = echoUs * 0.343f / 2.0f;
    Serial.print("echo_us="); Serial.print(echoUs);
    Serial.print(" | distance_mm="); Serial.print(mm, 0);
    Serial.println(mm < 20 || mm > 4000 ? " | OUT_OF_RANGE" : " | OK");
  }
  delay(PERIOD_MS);
}
