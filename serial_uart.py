import argparse
import time

import serial


# 泰山派板载 UART3。USB 转 TTL 通常使用 /dev/ttyUSB0。
SERIAL_PORT = "/dev/ttyS3"
BAUD_RATE = 9600
SEND_INTERVAL = 0.5


def open_serial(port=SERIAL_PORT):
    return serial.Serial(
        port=port,
        baudrate=BAUD_RATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )


def main():
    parser = argparse.ArgumentParser(description="每 500 ms 发送一次 ABCD")
    parser.add_argument("port", nargs="?", default=SERIAL_PORT, help="串口设备路径")
    args = parser.parse_args()

    try:
        with open_serial(args.port) as uart:
            while True:
                next_send = time.monotonic() + SEND_INTERVAL
                uart.write(b"ABCD")
                time.sleep(max(0, next_send - time.monotonic()))
    except KeyboardInterrupt:
        pass
    except serial.SerialException as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
