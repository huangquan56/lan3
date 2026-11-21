import serial
import time

# ===================== 串口参数（与 STM32 端一致）=====================
SERIAL_PORT = "/dev/ttyS3"
BAUDRATE = 9600
READ_TIMEOUT = 1

# ===================== 帧协议参数 =====================
FRAME_HEAD = b"@"            # 包头
FRAME_TAIL = b"\r\n"         # 包尾，两个字节

# 接收状态机的三个状态
STATE_WAIT_HEAD = 0          # 正在等包头 '@'
STATE_RECV_BODY = 1          # 正在收包体
STATE_WAIT_LF = 2            # 已收到 '\r'，等 '\n' 确认包尾

# ===================== 打开串口 =====================
ser = serial.Serial(
    port=SERIAL_PORT,
    baudrate=BAUDRATE,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=READ_TIMEOUT,
)

# ===================== 发送：手动组帧 =====================
payload = "START".encode("utf-8")          # 原始数据，字符串先转字节
frame = FRAME_HEAD + payload + FRAME_TAIL  # 拼出 b'@START\r\n'
ser.write(frame)
ser.flush()

# ===================== 接收：状态机逐字节解析 =====================
recv_state = STATE_WAIT_HEAD
recv_buf = bytearray()

while True:
    one_byte = ser.read(1)
    if not one_byte:
        # 读超时，没有新字节，继续等
        continue

    ch = one_byte[0]        # 取成 0~255 整数，方便和 ord() 比较

    if recv_state == STATE_WAIT_HEAD:
        # 状态一：只认包头，收到 '@' 才开始新一帧
        if ch == ord("@"):
            recv_buf = bytearray()
            recv_state = STATE_RECV_BODY

    elif recv_state == STATE_RECV_BODY:
        # 状态二：收包体；遇到 '\r' 先进入"等\n"状态
        if ch == ord("\r"):
            recv_state = STATE_WAIT_LF
        elif ch == ord("@"):
            # 包体中途又来一个包头，判定旧帧作废、从头开始收
            recv_buf = bytearray()
        else:
            recv_buf.append(ch)

    elif recv_state == STATE_WAIT_LF:
        # 状态三：'\r' 后面必须跟 '\n' 才算一帧完整
        if ch == ord("\n"):
            frame_data = bytes(recv_buf)          # 这就是去掉头尾的纯包体
            print("收到完整包：", frame_data)
            # 业务处理写这里，例如 frame_data.decode("utf-8")
            recv_buf = bytearray()
            recv_state = STATE_WAIT_HEAD
        else:
            # '\r' 后面不是 '\n'，说明那个 '\r' 只是普通数据，补回缓冲区
            recv_buf.append(ord("\r"))
            recv_buf.append(ch)
            recv_state = STATE_RECV_BODY

    time.sleep(0.005)

