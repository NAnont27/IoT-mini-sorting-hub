"""BH1750 bench test on Raspberry Pi I2C bus 1, ADDR tied to GND."""
import time
from smbus2 import SMBus, i2c_msg

ADDRESS = 0x23


def main():
    with SMBus(1) as bus:
        bus.write_byte(ADDRESS, 0x01)  # Power on.
        bus.write_byte(ADDRESS, 0x10)  # Continuous high-resolution mode.
        time.sleep(0.2)
        print("BH1750 READY | Ctrl+C to stop", flush=True)
        while True:
            message = i2c_msg.read(ADDRESS, 2)
            bus.i2c_rdwr(message)
            data = list(message)
            raw = (data[0] << 8) | data[1]
            lux = raw / 1.2  # Default measurement-time setting.
            print(f"raw={raw} | light_lux={lux:.2f}", flush=True)
            time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped")
    except OSError as error:
        print(f"I2C ERROR: {error}")
        raise SystemExit(1)
