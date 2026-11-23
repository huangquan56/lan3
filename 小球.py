import cv2
import numpy as np

from 二维码 import read_QR_one,TASK_a,TASK_b,TASK_c
import time
import serial

from serial_uart import open_serial

DEBUG=False

# TASK_a 编号对应颜色：1=红  2=绿  3=蓝
# 格式：{任务编号: (下限HSV, 上限HSV)}
COLOR_MAP = {
    1: (np.array([0, 120, 80]),  np.array([10, 255, 255])),   # 红色小球
    2: (np.array([35, 100, 60]), np.array([77, 255, 255])),   # 绿色小球
    3: (np.array([90, 110, 60]), np.array([125, 255, 255]))   # 蓝色小球
}
MIN=300
STABLE_COUNT=5
ALIGN_TOLERANCE = 15# 左右对准容差（像素），越小精度越高
GRAB_MAX_FRAME = 500   # 抓取最大循环帧数，超时防死循环

# TASK_b 编号对应颜色：1=红  2=绿  3=蓝  4=浅蓝  5=深蓝  6=黑
COLOR_MAP2 = {
    1: (np.array([0, 120, 80]),   np.array([10, 255, 255])),   # 红色
    2: (np.array([20, 100, 80]),  np.array([35, 255, 255])),   # 黄色
    3: (np.array([35, 100, 60]),  np.array([77, 255, 255])),   # 绿色
    4: (np.array([85, 80, 100]),  np.array([100, 255, 255])),  # 浅蓝色
    5: (np.array([100, 120, 60]), np.array([130, 255, 255])),  # 深蓝色
    6: (np.array([0, 0, 0]),      np.array([180, 255, 60]))    # 黑色
}
RESCUE_MIN_AREA = 500       # 救援目标最小轮廓面积，按实际画面大小调整
RESCUE_TOLERANCE = 15       # 对准容差（像素），越小精度越高
RESCUE_MAX_FRAME = 600      # 任务最大循环帧数，超时防死循环

BOX_LOW = np.array([0, 0, 0])
BOX_HIGH = np.array([180, 255, 60])
MIN_BOX_AREA = 400
BOX_MAX_FRAME = 600
BOX_TOLERANCE = 15

CMD_LEFT = "LEFT"
CMD_RIGHT = "RIGHT"
CMD_GO = "GO"
CMD_BACK = "BACK"
CMD_STOP = "STOP"
CMD_GRAB = "GRAB"

def init_serial():
    """
    初始化串口对象
    返回值：成功返回串口实例ser；失败返回None
    """
    try:
        return open_serial()
    except serial.SerialException as e:
        if DEBUG:
            print(f"SERIAL_OPEN_FAIL:{e}")
        return None

def send(ser,msg):                #ser：串口实例
                                  #msg：要发送的内容字符串
    if ser is not None and ser.is_open:
        send_str=str(msg)+"\n"
        ser.write(send_str.encode("utf-8"))

def qiu():#只检测
    if TASK_a not in COLOR_MAP:
        return False
    low,high=COLOR_MAP[TASK_a]
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False
    stable_frame=0
    find_flag=False
    for _ in range(150):
        ret, frame = cap.read()
        if not ret:
            continue
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv,low,high)
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        have_target=False
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= MIN:
                have_target=True
                break
        if have_target:
            stable_frame+=1
        else:
            stable_frame=0
        if stable_frame>STABLE_COUNT:
            find_flag=True
            break
    cap.release()
    return find_flag

def qiu_xy(ser):
    if TASK_a not in COLOR_MAP:
        send(ser, CMD_STOP)
        return "T2_fail_task"  # 任务参数错误/未执行T1
    low, high= COLOR_MAP[TASK_a]
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        send(ser, CMD_STOP)
        return "T2_fail_cam"

    stable_frame = 0
    align_ok = False
    frame_width = None
    mid_x = 0

    for _ in range(GRAB_MAX_FRAME):
        ret, frame = cap.read()
        if not ret:
            continue

        if frame_width is None:
            frame_width = frame.shape[1]
            mid_x = frame_width // 2
            # 如果摄像头与爪子有偏移，在这里补偿，例：mid_x = frame_width//2 -20

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, low, high)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        have_target = False
        target_cx = 0
        target_area = 0

        # 找最大的符合条件的轮廓
        valid_cnts = [cnt for cnt in contours if cv2.contourArea(cnt) >= MIN]
        if valid_cnts:
            max_cnt = max(valid_cnts, key=cv2.contourArea)
            # 计算目标中心点
            M = cv2.moments(max_cnt)
            if M["m00"] == 0:
                stable_frame = 0
                send(ser, CMD_STOP)
                continue

            have_target = True
            target_cx = int(M["m10"] / M["m00"])
            target_cy = int(M["m01"] / M["m00"])

        # 防抖：连续识别到才算真目标
        if have_target:
            stable_frame += 1
        else:
            stable_frame = 0
            continue

        if stable_frame >= STABLE_COUNT:
            offset = abs(target_cx - mid_x)
            if target_cx>=mid_x:
                if offset>=ALIGN_TOLERANCE:
                    send(ser,CMD_BACK)
                else:
                    send(ser,CMD_STOP)
                    align_ok=True
                    break
            else:
                if offset>=ALIGN_TOLERANCE:
                    send(ser,CMD_GO)
                else:
                    send(ser,CMD_STOP)
                    align_ok = True
                    break
    cap.release()
    send(ser, CMD_STOP)
    return "T2_ok"if align_ok else "T2_fail_timeout"


def find_box(ser):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        send(ser, CMD_STOP)
        return "T3_fail_cam"
    stable_frame = 0
    arrive_flag= False
    frame_width = None
    mid_x = 0

    for _ in range(BOX_MAX_FRAME):
        ret, frame = cap.read()
        if not ret:
            continue
        if frame_width is None:
            frame_width = frame.shape[1]
            mid_x = frame_width // 2
            # 如果摄像头和机械臂偏移：mid_x = frame_width//2 +20

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask_box = cv2.inRange(hsv, BOX_LOW, BOX_HIGH)
        contours, _ = cv2.findContours(mask_box, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        have_box = False
        box_cx = 0

        valid_box = [c for c in contours if cv2.contourArea(c) >= MIN_BOX_AREA]
        if valid_box:
            max_c = max(valid_box, key=cv2.contourArea)
            M = cv2.moments(max_c)
            if M["m00"] == 0:
                stable_frame = 0
                continue
            have_box = True
            box_cx = int(M["m10"] / M["m00"])
            box_cy = int(M["m01"] / M["m00"])

        # 防抖
        if have_box:
            stable_frame += 1
        else:
            stable_frame = 0
            send(ser, CMD_STOP)  # 丢目标立刻停车
            continue

        if stable_frame >= STABLE_COUNT:
            offset = abs(box_cx - mid_x)
            if box_cx>=mid_x:
                if offset>=BOX_TOLERANCE:
                    send(ser,CMD_BACK)
                else:
                    send(ser,CMD_STOP)
                    arrive_flag = True
                    break
            else:
                if offset>=BOX_TOLERANCE:
                    send(ser,CMD_GO)
                else:
                    send(ser,CMD_STOP)
                    arrive_flag = True
                    break

    cap.release()
    send(ser, CMD_STOP)
    return "T3_ok"


def car_stop():
    pass


def run_task():
    ok=read_QR_one(8)
    if ok:
        ret_text=f"OK:{TASK_a},{TASK_b},{TASK_c}"
        return True,ret_text
    else:
        return False,"QR_fail"
def run_task2(ser):
    res=qiu_xy(ser)
    return res


def run_task3(ser):
    res=find_box(ser)
    return res



def run_task4():
    return






def main():
    ser = init_serial()
    if ser is None:
        return
    while True:
        if ser is not None and ser.in_waiting>0:
            raw_data = ser.readline()
            try:
                cmd = raw_data.decode("utf-8").strip()
            except Exception:
                continue
            if cmd=="QR":            #扫码
                _,res=run_task()
                send(ser,res)
            elif cmd=="T2":          #找球
                res=run_task2(ser)
                send(ser,res)
            elif cmd=="T3":          #找桶
                res=run_task3(ser)
                send(ser,res)
            elif cmd=="T4":
                res=run_task4()
                send(ser,res)

            elif cmd=="STOP":
                car_stop()
                break
        time.sleep(0.01)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # SSH按下Ctrl+C手动终止程序，进入这里，不打印多余信息
        pass
    except Exception as err:
        # 捕获程序运行中未知崩溃，调试模式输出错误信息
        if DEBUG:
            print(f"PROG_ERR:{err}")
    finally:
        # 【无论程序如何退出都一定会执行】
        # Ctrl+C退出、异常崩溃、正常收到STOP退出，都会调用停止机构，保护硬件
        car_stop()













