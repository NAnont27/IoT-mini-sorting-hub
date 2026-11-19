// ESP32-S3: GPIO11 monitors a verified 3.3 V-compatible E18 NPN NO output.
// Do NOT connect an unverified 5 V output directly to ESP32.
// V2: +5V--1k--E18 OUT--10k--GPIO11--15k--GND; common grounds.
constexpr int SENSOR_PIN = 11;
constexpr unsigned long DEBOUNCE_MS = 30;

int lastReading = HIGH;
int reportedState = -1;
unsigned long changedAt = 0;

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_PIN, INPUT);
  delay(1000);
  lastReading = digitalRead(SENSOR_PIN);
  changedAt = millis();
  Serial.println("E18 TEST | GPIO11 | LOW=DETECTED, HIGH=CLEAR");
}

void loop() {
  const int reading = digitalRead(SENSOR_PIN);
  const unsigned long now = millis();
  if (reading != lastReading) {
    lastReading = reading;
    changedAt = now;
  }
  if (now - changedAt >= DEBOUNCE_MS && reading != reportedState) {
    reportedState = reading;
    Serial.println(reading == LOW ? "DETECTED" : "CLEAR");
  }
}
