// ESP32-S3: SDA -> GPIO12, SCL -> GPIO13.
// Diagnostic only; no external sensor library required.
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(12, 13);
  Wire.setClock(100000);
  Serial.println("I2C SCANNER READY | SDA=8 SCL=9");
}

void loop() {
  int found = 0;
  Serial.println("Scanning...");

  for (int address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    const byte result = Wire.endTransmission();
    if (result == 0) {
      Serial.print("FOUND 0x");
      if (address < 16) Serial.print('0');
      Serial.println(address, HEX);
      ++found;
    }
  }

  if (found == 0) Serial.println("NO I2C DEVICE FOUND");
  Serial.println("Scan complete");
  delay(3000);
}
