import argparse

import serial


# 泰山派板载 UART3。USB 转 TTL 通常使用 /dev/ttyUSB0。
SERIAL_PORT = "/dev/ttyS3"
BAUD_RATE = 9600
TEST_FRAME = b"@ABCD\r\n"


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


def echo_test_frames(uart):
    matched = 0
    while True:
        received = uart.read(1)
        if not received:
            continue

        if received == TEST_FRAME[matched:matched + 1]:
            matched += 1
            if matched == len(TEST_FRAME):
                uart.write(TEST_FRAME)
                matched = 0
        else:
            matched = int(received == b"@")


def main():
    parser = argparse.ArgumentParser(description="收到完整的 @ABCD 帧后原样回传")
    parser.add_argument("port", nargs="?", default=SERIAL_PORT, help="串口设备路径")
    args = parser.parse_args()

    try:
        with open_serial(args.port) as uart:
            echo_test_frames(uart)
    except KeyboardInterrupt:
        pass
    except serial.SerialException as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
