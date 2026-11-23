import serial


SERIAL_PORT = "/dev/ttyS3"
BAUDRATE = 9600
FRAME_HEAD = b"@"
FRAME_TAIL = b"\r\n"
MAX_PAYLOAD = 99  # STM32 的 100 字节接收缓冲区需要留 1 字节给字符串结束符。


class SerialLink:
    # 打开串口。用法：link = SerialLink()，也可用 SerialLink(port="/dev/ttyS3", baudrate=9600)。
    # timeout 是单次读取等待下一个字节的秒数。
    def __init__(self, port=SERIAL_PORT, baudrate=BAUDRATE, timeout=1):
        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
        )
        self._frame = None

    # 发送一帧。用法：link.send("ABCD") 或 link.send(b"ABCD")。
    # 只传包体，函数会自动加上 @ 和 CRLF。字符串按 UTF-8 编码。
    def send(self, payload):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        if len(payload) > MAX_PAYLOAD:
            raise ValueError(f"包体最多 {MAX_PAYLOAD} 字节")
        if any(marker in payload for marker in (FRAME_HEAD, b"\r", b"\n", b"\0")):
            raise ValueError("包体不能包含 @、回车、换行或空字符")

        self._serial.write(FRAME_HEAD + payload + FRAME_TAIL)
        self._serial.flush()

    # 接收一帧。用法：payload = link.receive()，收到 @ABCD\r\n 时返回 b"ABCD"。
    # 等待下一个字节超时时返回 None，已收到的半帧会留到下次调用继续接收。
    def receive(self):
        while True:
            incoming = self._serial.read(1)
            if not incoming:
                return None

            if incoming == FRAME_HEAD:
                self._frame = bytearray()
                continue
            if self._frame is None:
                continue

            if self._frame.endswith(FRAME_TAIL[:1]):
                payload = bytes(self._frame[:-1])
                self._frame = None
                if incoming == FRAME_TAIL[1:]:
                    return payload
                continue

            if incoming in (b"\n", b"\0") or (
                len(self._frame) == MAX_PAYLOAD and incoming != FRAME_TAIL[:1]
            ):
                self._frame = None
                continue

            self._frame.extend(incoming)

    # 关闭串口。用法：在程序退出时调用 link.close()，释放串口设备。
    def close(self):
        self._serial.close()
