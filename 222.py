import serial

SERIAL_PORT = "/dev/ttyS3"
BAUDRATE = 9600
TEST_FRAME = b"@ABCD\r\n"


def main():
    with serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1,
    ) as ser:
        print(f"Listening on {SERIAL_PORT} for {TEST_FRAME!r}", flush=True)
        matched = 0

        while True:
            incoming = ser.read(1)
            if not incoming:
                continue

            byte = incoming[0]
            if byte == TEST_FRAME[matched]:
                matched += 1
            else:
                # A new header can start a frame even after a partial match.
                matched = 1 if byte == TEST_FRAME[0] else 0

            if matched == len(TEST_FRAME):
                ser.write(TEST_FRAME)
                ser.flush()
                print(f"RX {TEST_FRAME!r}, TX {TEST_FRAME!r}", flush=True)
                matched = 0


if __name__ == "__main__":
    main()
