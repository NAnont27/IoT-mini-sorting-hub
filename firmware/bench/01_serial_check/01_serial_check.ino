// Step 1: USB upload and serial test only. No peripherals required.

unsigned long counter = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("MINI SORTING HUB - ESP32 SERIAL TEST");
}

void loop() {
  Serial.print("ESP32 OK | count=");
  Serial.print(counter++);
  Serial.print(" | uptime_ms=");
  Serial.println(millis());
  delay(1000);
}
