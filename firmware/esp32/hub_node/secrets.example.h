#pragma once
// Copy to secrets.h (same folder), then fill values; do not commit secrets.h.
constexpr char WIFI_SSID[] = "YOUR_2_4_GHZ_WIFI";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";
constexpr char MQTT_HOST[] = "192.168.1.100";  // Actual Pi LAN IP, not localhost.
constexpr unsigned short MQTT_PORT = 1883;
constexpr char MQTT_USER[] = "hub";
constexpr char MQTT_PASSWORD[] = "CHANGE_ME";
