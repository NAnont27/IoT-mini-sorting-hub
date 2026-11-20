// ESP32-S3 standalone, UNLOADED positional-servo end-to-end test.
// Sweeps 1000 us -> 2000 us (one end), holds, then back to 1000 us, repeat.
// GPIO6 -> servo signal. GPIO7 taps that wire AT the servo connector.
// GPIO7 is an input here: disconnect any other servo/device from it.
// Never connect GPIO7 to 5V; remove the GPIO6/7 tap before combined firmware.
// Servo: external regulated 5V, common GND. ESP32: USB power.
// Pulse widths are NOT calibrated physical angles. No rail/horn load attached.
#include <Arduino.h>
#include <ESP32Servo.h>

constexpr int SIGNAL_PIN = 6;
constexpr int MONITOR_PIN = 7;
// 1000-2000 us gave only ~90 deg on MG996R. Wider range for ~180 deg.
// If the servo buzzes/stalls at an end, move that limit back toward 1500.
constexpr int MIN_US = 600;
constexpr int MAX_US = 2400;
constexpr int STEP_US = 10;          // 100 steps per side
constexpr uint32_t STEP_MS = 20;     // ~2 s per full travel
constexpr uint32_t END_HOLD_MS = 1000;
constexpr uint32_t REPORT_MS = 500;

Servo servo;
bool ready = false;
bool automatic = true;
int commandUs = 1500;
int direction = +1;
bool holding = false;
uint32_t lastStep = 0;
uint32_t holdStart = 0;
uint32_t lastReport = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  pinMode(MONITOR_PIN, INPUT_PULLDOWN);
  servo.setPeriodHertz(50);
  servo.attach(SIGNAL_PIN, MIN_US, MAX_US);
  ready = servo.attached();
  if (!ready) {
    Serial.println("ERROR: PWM attach failed");
    return;
  }
  servo.writeMicroseconds(commandUs);
  lastStep = lastReport = millis();
  Serial.print("END-TO-END TEST | "); Serial.print(MIN_US);
  Serial.print(" <-> "); Serial.print(MAX_US);
  Serial.println(" us | hold 1 s at each end");
  Serial.println("s=pause at command (PWM remains), r=resume | pulse evidence only");
}

void loop() {
  if (!ready) return;
  while (Serial.available()) {
    const char c = Serial.read();
    if (c == 's' || c == 'S') {
      automatic = false;
      Serial.println("PAUSED: PWM remains; switch off adapter to de-energize");
    } else if (c == 'r' || c == 'R') {
      automatic = true;
      lastStep = millis();
      holdStart = millis();
      Serial.println("RESUMED");
    }
  }

  const uint32_t now = millis();
  if (automatic) {
    if (holding) {
      if (uint32_t(now - holdStart) >= END_HOLD_MS) {
        holding = false;
        direction = -direction;
        lastStep = now;
        Serial.println(direction > 0 ? "MOVE -> MAX_US" : "MOVE -> MIN_US");
      }
    } else if (uint32_t(now - lastStep) >= STEP_MS) {
      lastStep = now;
      commandUs = constrain(commandUs + direction * STEP_US, MIN_US, MAX_US);
      servo.writeMicroseconds(commandUs);
      if (commandUs == MIN_US || commandUs == MAX_US) {
        holding = true;
        holdStart = now;
        Serial.print("END_REACHED_COMMAND_US=");
        Serial.println(commandUs);
      }
    }
  }

  if (uint32_t(now - lastReport) >= REPORT_MS) {
    lastReport = now;
    const int expected = servo.readMicroseconds();
    const unsigned long measured = pulseIn(MONITOR_PIN, HIGH, 50000UL);
    const long error = static_cast<long>(measured) - expected;
    Serial.print("expected_us="); Serial.print(expected);
    Serial.print(" | measured_us="); Serial.print(measured);
    if (measured == 0) Serial.println(" | NO_PULSE");
    else if (error >= -100 && error <= 100) Serial.println(" | PULSE_MATCH");
    else Serial.println(" | PULSE_MISMATCH");
  }
}
