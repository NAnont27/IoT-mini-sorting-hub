"""Pi directly reads AS5600 + BH1750, then publishes actual measurements via MQTT."""
import json
import os
import time
import uuid
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from smbus2 import SMBus, i2c_msg

load_dotenv(Path(__file__).with_name(".env"))


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="hub-pi-sensors")
    client.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASSWORD"])
    client.connect(os.getenv("MQTT_HOST", "127.0.0.1"), int(os.getenv("MQTT_PORT", "1883")))
    client.loop_start()
    session = uuid.uuid4().hex
    start = time.monotonic()
    seq = 0
    light_started = False
    with SMBus(1) as bus:
        try:
            while True:
                payload = {"schema_version": 1, "device_id": "gateway-01",
                           "session_id": session, "seq": seq,
                           "uptime_ms": int((time.monotonic() - start) * 1000),
                           "angle_valid": False, "light_valid": False}
                try:
                    status = bus.read_byte_data(0x36, 0x0B)
                    payload["magnet_status"] = status
                    payload["angle_valid"] = bool(status & 0x20) and not bool(status & 0x18)
                    if payload["angle_valid"]:
                        data = bus.read_i2c_block_data(0x36, 0x0C, 2)
                        payload["angle_deg"] = (((data[0] << 8) | data[1]) & 0xFFF) * 360 / 4096
                except OSError as exc:
                    payload["angle_error"] = str(exc)
                try:
                    if not light_started:
                        bus.write_byte(0x23, 0x01)
                        bus.write_byte(0x23, 0x10)
                        time.sleep(0.2)
                        light_started = True
                    message = i2c_msg.read(0x23, 2)
                    bus.i2c_rdwr(message)
                    data = list(message)
                    payload["light_lux"] = ((data[0] << 8) | data[1]) / 1.2
                    payload["light_valid"] = True
                except OSError as exc:
                    light_started = False
                    payload["light_error"] = str(exc)
                client.publish("sorter/gateway", json.dumps(payload), qos=1, retain=False)
                seq += 1
                time.sleep(0.25)
        finally:
            client.disconnect()
            client.loop_stop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
