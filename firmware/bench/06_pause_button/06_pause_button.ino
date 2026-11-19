// ESP32-S3: normally-open push button between GPIO10 and GND.
// Bench test only: toggles printed state; does not control any actuator.
constexpr int BUTTON_PIN = 10;
constexpr unsigned long DEBOUNCE_MS = 40;

bool paused = false;
int lastReading = HIGH;
int stableState = HIGH;
unsigned long changedAt = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  delay(1000);
  lastReading = digitalRead(BUTTON_PIN);
  stableState = lastReading;
  changedAt = millis();
  Serial.println("BUTTON TEST READY | press to toggle PAUSED/READY");
  Serial.println("Bench only; no motor control");
}

void loop() {
  const int reading = digitalRead(BUTTON_PIN);
  const unsigned long now = millis();
  if (reading != lastReading) {
    changedAt = now;
    lastReading = reading;
  }
  if (now - changedAt >= DEBOUNCE_MS && reading != stableState) {
    stableState = reading;
    if (stableState == LOW) {
      paused = !paused;
      Serial.println(paused ? "PAUSED" : "READY");
    }
  }
}
