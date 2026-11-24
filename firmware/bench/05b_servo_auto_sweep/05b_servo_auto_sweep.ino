// ESP32-S3 standalone test: unloaded positional servo, automatic 60-120 sweep.
// GPIO6 -> servo signal; GPIO7 taps that signal at the servo connector.
// Never connect GPIO7 to +5V. Remove this tap before using combined firmware.
// External regulated 5V servo supply; common GND with ESP32. ESP32 uses USB.
// s = pause at the commanded position (PWM remains); r = resume sweep.
// Pulse measurement is NOT servo position feedback or a supply-voltage test.
#include <Arduino.h>
#include <ESP32Servo.h>

constexpr int SERVO_SIGNAL = 6;
constexpr int SIGNAL_MONITOR = 7;
constexpr int MIN_ANGLE = 60;
constexpr int MAX_ANGLE = 120;
constexpr uint32_t STEP_MS = 30;
constexpr uint32_t REPORT_MS = 500;

Servo testServo;
bool pwmAttached = false;
bool sweeping = true;
int angle = 90;
int direction = 1;
uint32_t lastStep = 0;
uint32_t lastReport = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  pinMode(SIGNAL_MONITOR, INPUT_PULLDOWN);
  testServo.setPeriodHertz(50);
  testServo.attach(SERVO_SIGNAL, 1000, 2000);
  pwmAttached = testServo.attached();
  if (!pwmAttached) {
    Serial.println("ERROR: PWM attach failed");
    return;
  }
  testServo.write(angle);
  lastStep = lastReport = millis();
  Serial.println("AUTO SWEEP 60-120 | s=pause, r=resume | GPIO6 -> GPIO7 tap");
  Serial.println("PWM evidence only; no position, power or current feedback");
}

void loop() {
  if (!pwmAttached) return;

  while (Serial.available()) {
    const char command = Serial.read();
    if (command == 's' || command == 'S') {
      sweeping = false;
      Serial.println("PAUSED: PWM holds current command; cut servo power to de-energize");
    } else if (command == 'r' || command == 'R') {
      sweeping = true;
      lastStep = millis();
      Serial.println("RESUMED");
    }
  }

  const uint32_t now = millis();
  if (sweeping && uint32_t(now - lastStep) >= STEP_MS) {
    lastStep = now;
    if (angle >= MAX_ANGLE) direction = -1;
    else if (angle <= MIN_ANGLE) direction = 1;
    angle += direction;
    testServo.write(angle);
  }

  if (uint32_t(now - lastReport) >= REPORT_MS) {
    lastReport = now;
    const int expectedUs = testServo.readMicroseconds();
    const unsigned long measuredUs = pulseIn(SIGNAL_MONITOR, HIGH, 50000UL);
    const long difference = static_cast<long>(measuredUs) - expectedUs;
    Serial.print(sweeping ? "SWEEP" : "PAUSED");
    Serial.print(" | nominal_angle="); Serial.print(angle);
    Serial.print(" | expected_us="); Serial.print(expectedUs);
    Serial.print(" | measured_us="); Serial.print(measuredUs);
    if (measuredUs == 0) Serial.println(" | NO_PULSE");
    else if (difference >= -100 && difference <= 100) Serial.println(" | PULSE_MATCH");
    else Serial.println(" | PULSE_MISMATCH");
  }
}
