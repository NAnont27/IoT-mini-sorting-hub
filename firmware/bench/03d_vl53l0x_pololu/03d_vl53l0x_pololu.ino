// ESP32-S3: VL53L0X distance test with the Pololu VL53L0X library
// (Library Manager: "VL53L0X" by Pololu). SDA=GPIO8, SCL=GPIO9.
// Purpose: check whether this module works when the Adafruit library fails.
#include <Wire.h>
#include <VL53L0X.h>

VL53L0X sensor;
bool ready = false;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(8, 9);
  Wire.setClock(100000);
  sensor.setBus(&Wire);
  sensor.setTimeout(500);
  ready = sensor.init();
  if (!ready) {
    Serial.println("POLOLU INIT FAILED");
    return;
  }
  sensor.startContinuous(100);
  Serial.println("POLOLU VL53L0X READY - distance unit: mm");
}

void loop() {
  if (!ready) {
    delay(1000);
    return;
  }
  const uint16_t mm = sensor.readRangeContinuousMillimeters();
  if (sensor.timeoutOccurred()) Serial.println("TIMEOUT");
  else if (mm >= 8190) Serial.println("OUT_OF_RANGE");
  else { Serial.print("distance_mm="); Serial.println(mm); }
  delay(250);
}
