// ESP32-S3: four E18 NPN NO sensors, regulated 5 V supplies.
// Each channel needs its own: +5V--1k--OUT--10k--GPIO--15k--GND.
// Brown -> +5V; blue -> common GND. Never connect raw 5 V OUT to GPIO.
constexpr int IR_PINS[] = {11, 12, 13, 14};
const char* IR_NAMES[] = {"tray_exit", "A", "B", "HOLD"};

void setup() {
  Serial.begin(115200);
  for (int pin : IR_PINS) pinMode(pin, INPUT);
  delay(1000);
  Serial.println("E18 x4 V2 | LOW=DETECTED HIGH=CLEAR | R network required");
}

void loop() {
  for (int i = 0; i < 4; ++i) {
    const int raw = digitalRead(IR_PINS[i]);
    Serial.print(IR_NAMES[i]);
    Serial.print("=");
    Serial.print(raw);
    Serial.print(raw == LOW ? "(DETECTED)" : "(CLEAR)");
    if (i < 3) Serial.print(" | ");
  }
  Serial.println();
  delay(200);
}
