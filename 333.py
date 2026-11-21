import serial

ser = serial.Serial(
    port="/dev/ttyS3",
    baudrate=9600,
    bytesize=8,
    parity=serial.PARITY_NONE,
    stopbits=1
)

def send_command(command):
    ser.write((command + "\n").encode("ascii"))

# 视觉识别到右转
send_command("R")
# 视觉识别到左转
send_command("L")
