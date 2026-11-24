// ESP32-S3: identify the chip answering at I2C 0x29 (SDA=GPIO12, SCL=GPIO13).
// Read-only register check; does not configure or calibrate the sensor.
// VL53L0X: reg 0xC0=0xEE, 0xC1=0xAA, 0xC2=0x10
// VL53L1X: 16-bit reg 0x010F..0x0110 = 0xEA 0xCC
#include <Wire.h>

constexpr uint8_t ADDR = 0x29;

// Uses a STOP between the register write and the read (no repeated start),
// and reports the Wire error code so a failed read is never shown as data.
int lastTx = 0, lastRx = 0;

int read8(uint8_t reg) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  lastTx = Wire.endTransmission(true);
  if (lastTx != 0) return -1;
  delay(2);
  lastRx = Wire.requestFrom(ADDR, (uint8_t)1);
  if (lastRx != 1) return -1;
  return Wire.read();
}

bool read16reg(uint16_t reg, uint8_t &a, uint8_t &b) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg >> 8);
  Wire.write(reg & 0xFF);
  lastTx = Wire.endTransmission(true);
  if (lastTx != 0) return false;
  delay(2);
  lastRx = Wire.requestFrom(ADDR, (uint8_t)2);
  if (lastRx != 2) return false;
  a = Wire.read();
  b = Wire.read();
  return true;
}

void printHex(int v) {
  if (v < 0) { Serial.print("ERR"); return; }
  Serial.print("0x");
  if (v < 0x10) Serial.print('0');
  Serial.print(v, HEX);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(12, 13);
  Wire.setClock(100000);
  Serial.println("TOF ID CHECK | addr 0x29 | SDA=8 SCL=9");
}

void loop() {
  const int c0 = read8(0xC0), c1 = read8(0xC1), c2 = read8(0xC2);
  Serial.print("L0X regs C0/C1/C2 = ");
  printHex(c0); Serial.print(' '); printHex(c1); Serial.print(' '); printHex(c2);
  if (c0 == 0xEE && c1 == 0xAA && c2 == 0x10) Serial.print(" -> VL53L0X ID OK");
  if (c2 < 0) { Serial.print(" | tx="); Serial.print(lastTx); Serial.print(" rx="); Serial.print(lastRx); }
  Serial.println();

  uint8_t a = 0, b = 0;
  Serial.print("L1X reg 0x010F = ");
  if (read16reg(0x010F, a, b)) {
    printHex(a); Serial.print(' '); printHex(b);
    if (a == 0xEA && b == 0xCC) Serial.print(" -> VL53L1X detected (needs a VL53L1X library)");
  } else {
    Serial.print("ERR | tx="); Serial.print(lastTx); Serial.print(" rx="); Serial.print(lastRx);
  }
  Serial.println();
  Serial.println("---");
  delay(2000);
}
