import cv2
import numpy as np

import 二维码2
from 二维码2 import read_QR_one
import time
# 串口收发统一走 serial_link.py 的 SerialLink（自动加 @ 包头和 \r\n 包尾）
from serial_link import SerialLink

DEBUG=False
# 串口参数默认走 serial_link.py 里的配置（/dev/ttyS3，9600，8N1）
# 如需修改端口或波特率，直接改 serial_link.py 顶部的 SERIAL_PORT / BAUDRATE

# TASK_a 编号对应颜色：1=红  2=绿  3=蓝
# 格式：{任务编号: (下限HSV, 上限HSV)}
COLOR_MAP = {
    1: [[np.array([0, 120, 80]),  np.array([10, 255, 255])],[np.array([170, 120, 80]), np.array([180, 255, 255])]],   # 红色小球
    2: [[np.array([35, 100, 60]), np.array([77, 255, 255])]],   # 绿色小球
    3: [[np.array([90, 110, 60]), np.array([125, 255, 255])]]   # 蓝色小球
}
MIN=300
STABLE_COUNT=5
ALIGN_TOLERANCE = 15# 左右对准容差（像素），越小精度越高
GRAB_MAX_FRAME = 500   # 抓取最大循环帧数，超时防死循环

# TASK_b 编号对应颜色：1=红  2=绿  3=蓝  4=浅蓝  5=深蓝  6=黑
COLOR_MAP2 = {
    1: [[np.array([0, 120, 80]),   np.array([10, 255, 255])],[np.array([170, 120, 80]), np.array([180, 255, 255])]],   # 红色
    2: [[np.array([20, 100, 80]),  np.array([35, 255, 255])]],   # 黄色
    3: [[np.array([35, 100, 60]),  np.array([77, 255, 255])]],   # 绿色
    4: [[np.array([85, 80, 100]),  np.array([100, 255, 255])]],  # 浅蓝色
    5: [[np.array([100, 120, 60]), np.array([130, 255, 255])]],  # 深蓝色
    6: [[np.array([0, 0, 0]),      np.array([180, 255, 60])]]    # 黑色
}
RESCUE_MIN_AREA = 500       # 救援目标最小轮廓面积，按实际画面大小调整
RESCUE_TOLERANCE = 15       # 对准容差（像素），越小精度越高
RESCUE_MAX_FRAME = 600      # 任务最大循环帧数，超时防死循环

BOX_LOW = np.array([0, 0, 0])
BOX_HIGH = np.array([180, 255, 60])
MIN_BOX_AREA = 400
BOX_MAX_FRAME = 600
BOX_TOLERANCE = 15

# ========= T4转盘任务参数（水平侧视） =========
DISK_MAX_FRAME = 800        # 转盘任务最大帧数，防止卡死
DISK_MIN_AREA = 350
STATIC_THRESHOLD = 15       # 帧差灰度阈值
STATIC_PIXEL_CNT = 400      # 变动像素小于该值认为画面不动
STATIC_FRAME_CNT = 5       # 连续N帧不动判定转盘停稳

CMD_LEFT = "LEFT"
CMD_RIGHT = "RIGHT"
CMD_GO = "GO"
CMD_BACK = "BACK"
CMD_STOP = "STOP"
CMD_GRAB = "GRAB"

def send(link, msg):              # link：SerialLink 实例；msg：要发送的包体字符串
    if link is not None:
        # SerialLink.send 会自动加 @ 包头和 \r\n 包尾，这里只传包体即可
        link.send(str(msg))

def get_mask(hsv,ranges):
    mask_total = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for low, high in ranges:
        m = cv2.inRange(hsv, low, high)
        mask_total = cv2.bitwise_or(mask_total, m)
    return mask_total

def qiu():#只检测
    if 二维码2.TASK_a not in COLOR_MAP:
        return False
    ranges=COLOR_MAP[二维码2.TASK_a]
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
        mask = get_mask(hsv,ranges)
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

def qiu_xy(link):
    if 二维码2.TASK_a not in COLOR_MAP:
        send(link, CMD_STOP)
        return "T2_fail_task"  # 任务参数错误/未执行T1
    ranges= COLOR_MAP[二维码2.TASK_a]
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        send(link, CMD_STOP)
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
        mask = get_mask(hsv, ranges)
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
                send(link, CMD_STOP)
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
                    send(link, CMD_BACK)
                else:
                    send(link, CMD_STOP)
                    align_ok=True
                    break
            else:
                if offset>=ALIGN_TOLERANCE:
                    send(link, CMD_GO)
                else:
                    send(link, CMD_STOP)
                    align_ok = True
                    break
    cap.release()
    send(link, CMD_STOP)
    return "T2_ok"if align_ok else "T2_fail_timeout"


def find_box(link):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        send(link, CMD_STOP)
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
            send(link, CMD_STOP)  # 丢目标立刻停车
            continue

        if stable_frame >= STABLE_COUNT:
            offset = abs(box_cx - mid_x)
            if box_cx>=mid_x:
                if offset>=BOX_TOLERANCE:
                    send(link, CMD_BACK)
                else:
                    send(link, CMD_STOP)
                    arrive_flag = True
                    break
            else:
                if offset>=BOX_TOLERANCE:
                    send(link, CMD_GO)
                else:
                    send(link, CMD_STOP)
                    arrive_flag = True
                    break

    cap.release()
    send(link, CMD_STOP)
    return "T3_ok" if arrive_flag else "T3_fail_timeout"


def car_stop(link):
    send(link, CMD_STOP)


def run_task():
    ok=read_QR_one(8)
    if ok:
        ret_text=f"OK:{二维码2.TASK_a},{二维码2.TASK_b},{二维码2.TASK_c}"
        return True,ret_text
    else:
        return False,"QR_fail"
def run_task2(link):
    res=qiu_xy(link)
    return res


def run_task3(link):
    res=find_box(link)
    return res



def run_task4(link):
    if 二维码2.TASK_b not in COLOR_MAP2:
        return "4_FAIL"
    ranges = COLOR_MAP2[二维码2.TASK_b]
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "4_FAIL"

    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        return "4_FAIL"
    prev_gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
    static_cnt = 0
    disk_stable = False
    send_wait_flag = False     # 标记：有没有发过WAIT_TURN

    target_x = None

    for _ in range(DISK_MAX_FRAME):
        ret, frame = cap.read()
        if not ret:
            continue
        cur_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 帧差法判断转盘是否静止
        diff = cv2.absdiff(prev_gray, cur_gray)
        _, diff_bin = cv2.threshold(diff, STATIC_THRESHOLD, 255, cv2.THRESH_BINARY)
        change_pixel = np.sum(diff_bin > 0)

        if change_pixel < STATIC_PIXEL_CNT:
            static_cnt += 1
        else:
            static_cnt = 0
        disk_stable = (static_cnt >= STATIC_FRAME_CNT)
        prev_gray = cur_gray.copy()

        # 转盘在转动：发一次WAIT_TURN，之后不再重复发
        if not disk_stable:
            if not send_wait_flag:
                send(link, "WAIT_TURN")
                send_wait_flag = True
            continue

        # 重点：如果还没有发过WAIT_TURN，直接跳过识别，继续等
        if not send_wait_flag:
            continue

        # 已经发过WAIT_TURN + 转盘静止，开始识别目标
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = get_mask(hsv, ranges)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid = [c for c in contours if cv2.contourArea(c) >= DISK_MIN_AREA]

        if valid:
            max_c = max(valid, key=cv2.contourArea)
            M = cv2.moments(max_c)
            if M["m00"] != 0:
                target_x = int(M["m10"] / M["m00"])
                break

    cap.release()
    if target_x is not None:
        return f"DISK_X:{target_x}"
    else:
        return "4_FAIL"

def main():
    # 用 SerialLink 打开串口（参数默认走 serial_link.py 顶部配置）
    link = None
    try:
        link = SerialLink(timeout=0.1)
    except Exception as e:
        if DEBUG:
            print(f"SERIAL_OPEN_FAIL:{e}")
        return
    try:
        while True:
            # 接收一帧（SerialLink 自动解析 @...CRLF），收到包体 bytes，超时返回 None
            raw_data = link.receive()
            if raw_data is not None:
                try:
                    cmd = raw_data.decode("utf-8").strip()
                except Exception:
                    continue
                if cmd == "QR":  # 扫码
                    _, res = run_task()
                    send(link, res)
                elif cmd == "T2":  # 找球
                    res = run_task2(link)
                    send(link, res)
                elif cmd == "T3":  # 找桶
                    res = run_task3(link)
                    send(link, res)
                elif cmd == "T4":
                    res = run_task4(link)
                    send(link, res)
                elif cmd == "STOP":
                    car_stop(link)
                    break
            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    except Exception as err:
        if DEBUG:
            print(f"PROG_ERR:{err}")
    finally:
        # 崩溃、Ctrl+C、正常退出都会执行停车关闭串口
        if link is not None:
            car_stop(link)
            link.close()

if __name__ == "__main__":
    main()
#（注：内容由AI生成）



