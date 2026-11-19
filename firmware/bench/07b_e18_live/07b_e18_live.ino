// GPIO11 must receive a verified 3.3 V-compatible signal, NOT 5 V.
// V2: +5V--1k--E18 OUT--10k--GPIO11--15k--GND; common grounds.
constexpr int SENSOR_PIN = 11;

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_PIN, INPUT);
  delay(1000);
  Serial.println("E18 LIVE TEST | GPIO11");
}

void loop() {
  const int reading = digitalRead(SENSOR_PIN);
  Serial.print("raw=");
  Serial.print(reading);
  Serial.print(" | ");
  Serial.println(reading == LOW ? "DETECTED" : "CLEAR");
  delay(200);
}
