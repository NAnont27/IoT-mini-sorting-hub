"""Read AS5600 raw angle and magnet status; does not program OTP/config."""
import time
from smbus2 import SMBus

ADDRESS = 0x36


def main():
    with SMBus(1) as bus:
        print("AS5600 TEST | Ctrl+C to stop", flush=True)
        while True:
            status = bus.read_byte_data(ADDRESS, 0x0B)
            if not status & 0x20:
                print("NO_MAGNET", flush=True)
            elif status & 0x10:
                print("MAGNET_TOO_WEAK", flush=True)
            elif status & 0x08:
                print("MAGNET_TOO_STRONG", flush=True)
            else:
                data = bus.read_i2c_block_data(ADDRESS, 0x0C, 2)
                raw = ((data[0] << 8) | data[1]) & 0x0FFF
                angle = raw * 360.0 / 4096.0
                print(f"MAGNET_OK | raw={raw} | angle_deg={angle:.2f}", flush=True)
            time.sleep(0.3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped")
    except OSError as error:
        print(f"I2C ERROR: {error}")
        raise SystemExit(1)
