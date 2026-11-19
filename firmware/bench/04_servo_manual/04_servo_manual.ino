// Unloaded positional servo bench test, ESP32-S3 GPIO6.
// Servo power: separate regulated 5 V supply, common GND with ESP32.
// Install ESP32Servo. Commands: 1 / 2 / 3 select nominal 60 / 90 / 120.
#include <ESP32Servo.h>

Servo testServo;

void setup() {
  Serial.begin(115200);
  delay(1000);
  testServo.setPeriodHertz(50);
  testServo.attach(6, 1000, 2000);
  testServo.write(90);
  Serial.println("SERVO TEST | 1=60, 2=90, 3=120 (nominal angles)");
}

void loop() {
  if (!Serial.available()) return;
  const char command = Serial.read();
  int angle;
  if (command == '1') angle = 60;
  else if (command == '2') angle = 90;
  else if (command == '3') angle = 120;
  else return;

  testServo.write(angle);
  Serial.print("COMMAND_SENT | nominal_angle=");
  Serial.println(angle);
}
