// ESP32-S3-N16R8: SDA -> GPIO12, SCL -> GPIO13.
// Install Adafruit VL53L0X and its dependencies via Library Manager.
#include <Wire.h>
#include <Adafruit_VL53L0X.h>

Adafruit_VL53L0X sensor;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(12, 13);
  Wire.setClock(100000);

  if (!sensor.begin(0x29, false, &Wire)) {
    Serial.println("VL53L0X NOT FOUND - check power, SDA and SCL");
    while (true) {
      delay(1000);
    }
  }
  Serial.println("VL53L0X READY - distance unit: mm");
}

void loop() {
  VL53L0X_RangingMeasurementData_t measurement = {};
  const auto result = sensor.rangingTest(&measurement, false);

  if (result == VL53L0X_ERROR_NONE && measurement.RangeStatus == 0) {
    Serial.print("distance_mm=");
    Serial.println(measurement.RangeMilliMeter);
  } else {
    Serial.print("INVALID | api_error=");
    Serial.print(static_cast<int>(result));
    Serial.print(" | range_status=");
    Serial.println(measurement.RangeStatus);
  }
  delay(250);
}
