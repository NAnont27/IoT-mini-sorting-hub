// ESP32-S3 bench test: servo signal GPIO6, pulse monitor GPIO7.
// Tap GPIO7 onto the GPIO6 signal wire at the servo connector.
// GPIO7 must NEVER connect to the servo's 5 V power wire.
// Measures electrical pulses, NOT mechanical position or servo acknowledgement.
#include <ESP32Servo.h>

constexpr int SERVO_SIGNAL = 6;
constexpr int SIGNAL_MONITOR = 7;
Servo testServo;
bool pwmAttached = false;

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
  testServo.write(90);
  Serial.println("READY | 1=60, 2=90, 3=120 | GPIO6 signal -> GPIO7 monitor");
  Serial.println("PWM evidence only; no servo position feedback");
}

void loop() {
  if (!Serial.available()) return;
  const char command = Serial.read();
  if (command == '\r' || command == '\n') return;
  Serial.print("RX: ");
  Serial.println(command);
  if (!pwmAttached) {
    Serial.println("ERROR: PWM is not attached");
    return;
  }

  int angle;
  if (command == '1') angle = 60;
  else if (command == '2') angle = 90;
  else if (command == '3') angle = 120;
  else {
    Serial.println("Use 1, 2 or 3");
    return;
  }

  testServo.write(angle);
  delay(60);
  const int expectedUs = testServo.readMicroseconds();
  const unsigned long measuredUs = pulseIn(SIGNAL_MONITOR, HIGH, 50000UL);

  Serial.print("PWM_COMMAND | nominal_angle=");
  Serial.print(angle);
  Serial.print(" | expected_us=");
  Serial.println(expectedUs);
  Serial.print("PWM_MEASURED | high_us=");
  Serial.println(measuredUs);

  if (measuredUs == 0) {
    Serial.println("NO_PULSE: check GPIO7 tap and GPIO6 signal wiring");
  } else {
    const long difference = static_cast<long>(measuredUs) - expectedUs;
    if (difference >= -100 && difference <= 100) {
      Serial.println("PULSE_MATCH: signal observed, NOT proof of servo movement");
    } else {
      Serial.println("PULSE_MISMATCH: check wiring/timing; retry measurement");
    }
  }
}
