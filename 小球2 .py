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
T2_RECHECK_INTERVAL = 1.0  # T2每次发送GO/BACK后，等待1秒再重新识别判断
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

# ========= T4转盘任务参数（水平侧视：识别目标中心进入指定区域并静止4帧发ok） =========
DISK_MAX_FRAME = 800        # 转盘任务最大帧数，超时防卡死
DISK_MIN_AREA = 350         # 目标物体最小轮廓面积
DISK_CENTER_X_TOL = 20      # 中心点允许偏离画面中线的左右像素（±20）
DISK_TARGET_Y_RATIO = 0.75  # 目标纵向位置 = 画面高度 × 0.75（由上到下 3/4）
DISK_Y_TOL = 30             # 纵向位置允许的上下偏差（像素），按现场画面调
DISK_STILL_PIXEL = 6        # 相邻两帧中心点位移小于该值，视为“没动”
DISK_STILL_FRAME = 4        # 中心点在区域内且几乎不动，连续该帧数即发 ok

# ========= T5安置区任务参数（TASK_c 编号对应安置区颜色：1=红 2=蓝 3=黑）=========
ZONE_MAP = {
    1: [[np.array([0, 120, 80]),   np.array([10, 255, 255])],
        [np.array([170, 120, 80]), np.array([180, 255, 255])]],   # 红色安置区（两段）
    2: [[np.array([100, 120, 60]), np.array([130, 255, 255])]],  # 蓝色安置区
    3: [[np.array([0, 0, 0]),      np.array([180, 255, 60])]],   # 黑色安置区
}

ZONE_MIN_AREA = 400      # 安置区圆圈最小面积，现场按画面调
ZONE_TOLERANCE = 15      # 左右对准容差（像素）
ZONE_MAX_FRAME = 600     # 超时防死循环
ZONE_RECHECK_INTERVAL = 1.0  # 停车/修正后等待，再读新画面重新判断

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
    # T2新流程：电控移动搜索时，视觉持续识别二维码指定的目标颜色小球
    # 发现目标 -> 发STOP -> 判断左右偏差发GO/BACK -> 等1秒重新判断
    # 中心进入中线容差范围 -> 发STOP和ok2，结束任务
    if 二维码2.TASK_a not in COLOR_MAP:
        send(link, CMD_STOP)
        send(link, "T2_fail_task")
        return "T2_fail_task"

    # 只识别TASK_a指定的一种颜色，不会同时识别三个颜色
    ranges = COLOR_MAP[二维码2.TASK_a]
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        send(link, CMD_STOP)
        send(link, "T2_fail_cam")
        return "T2_fail_cam"

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
            # 摄像头与爪子有横向偏移时，在这里补偿，例如 mid_x = frame_width//2 - 20

        # 移动过程中也持续识别，不再要求先静止或连续多帧防抖
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = get_mask(hsv, ranges)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 过滤小噪点，并选择面积最大的目标小球
        valid_cnts = [cnt for cnt in contours if cv2.contourArea(cnt) >= MIN]
        if not valid_cnts:
            # 暂时没看到目标：不发送新命令，让电控保持当前移动搜索状态
            continue

        max_cnt = max(valid_cnts, key=cv2.contourArea)
        M = cv2.moments(max_cnt)
        if M["m00"] == 0:
            continue
        target_cx = int(M["m10"] / M["m00"])

        # 一旦发现目标，先通知电控停车，再根据中心位置决定下一步
        send(link, CMD_STOP)
        offset = abs(target_cx - mid_x)

        if offset <= ALIGN_TOLERANCE:
            # 小球中心已经到画面中线附近：保持停车并只发送一次ok2
            send(link, "ok2")
            align_ok = True
            break

        # 沿用原电控方向约定：目标在中线右侧发BACK，在左侧发GO
        if target_cx > mid_x:
            send(link, CMD_BACK)
        else:
            send(link, CMD_GO)

        # 给电控1秒调整时间，之后读取新画面重新判断
        time.sleep(T2_RECHECK_INTERVAL)

    cap.release()
    if not align_ok:
        # 超时仍未对准，停车并上报一次失败
        send(link, CMD_STOP)
        send(link, "T2_fail_timeout")
        return "T2_fail_timeout"
    return "ok2"

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


def find_zone(link):
    # 安置区：识别安置区圆圈颜色，左右对准到圆圈中心后停车
    if 二维码2.TASK_c not in ZONE_MAP:
        send(link, CMD_STOP)
        return "T5_fail_task"
    ranges = ZONE_MAP[二维码2.TASK_c]
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        send(link, CMD_STOP)
        return "T5_fail_cam"
    stable_frame = 0
    arrive_flag = False
    frame_width = None
    mid_x = 0

    # 搜索时由STM32沿路线移动；修正动作期间用此标记避免盲动
    target_acquired = False
    correction_active = False

    for _ in range(ZONE_MAX_FRAME):
        ret, frame = cap.read()
        if not ret:
            continue
        if frame_width is None:
            frame_width = frame.shape[1]
            mid_x = frame_width // 2
            # 如果摄像头和机械臂偏移：mid_x = frame_width//2 +20

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask_zone = get_mask(hsv, ranges)
        contours, _ = cv2.findContours(mask_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        have_zone = False
        zone_cx = 0

        valid_zone = [c for c in contours if cv2.contourArea(c) >= ZONE_MIN_AREA]
        if not valid_zone:
            stable_frame = 0
            # 搜索阶段不停车；修正时丢失目标则停车，避免盲动
            if correction_active:
                send(link, CMD_STOP)
                correction_active = False
            continue

        max_zone = max(valid_zone, key=cv2.contourArea)
        M = cv2.moments(max_zone)
        if M["m00"] == 0:
            stable_frame = 0
            continue
        zone_cx = int(M["m10"] / M["m00"])

       # 首次发现目标，或修正后重新看到目标：先停车，再读稳定后的画面
        if not target_acquired or correction_active:
            send(link, CMD_STOP)
            target_acquired = True
            correction_active = False
            stable_frame = 0
            time.sleep(ZONE_RECHECK_INTERVAL)
            continue

        # 连续识别到目标后再判断，降低误识别影响
        stable_frame += 1
        if stable_frame < STABLE_COUNT:
            continue

        offset = zone_cx - mid_x
        if abs(offset) <= ZONE_TOLERANCE:
            send(link, CMD_STOP)
            arrive_flag = True
            break

        # 保留原来的方向约定：目标偏右发BACK，偏左发GO
        if offset > 0:
            send(link, CMD_BACK)
        else:
            send(link, CMD_GO)

        correction_active = True
        stable_frame = 0
        time.sleep(ZONE_RECHECK_INTERVAL)

    cap.release()
    send(link, CMD_STOP)
    return "T5_ok" if arrive_flag else "T5_fail_timeout"


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
    # qiu_xy内部已经发送ok2或失败报文，这里只执行任务，不重复发送
    return qiu_xy(link)


def run_task3(link):
    res=find_box(link)
    return res



def run_task4(link):
    # T4 的返回报文统一在函数内部发送，main 里不再重复发送
    # 校验：TASK_b 必须是 1~6
    if 二维码2.TASK_b not in COLOR_MAP2:
        send(link, "4_FAIL")
        return "4_FAIL"
    ranges = COLOR_MAP2[二维码2.TASK_b]
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        send(link, "4_FAIL")
        return "4_FAIL"

    still_cnt = 0              # 区域内静止连续帧计数
    prev_cx = None             # 上一帧中心 x
    prev_cy = None             # 上一帧中心 y
    frame_h = None
    frame_w = None
    ok_sent = False

    for _ in range(DISK_MAX_FRAME):
        ret, frame = cap.read()
        if not ret:
            continue

        if frame_w is None:
            frame_h, frame_w = frame.shape[:2]

        # 目标区域：中线 = 画面宽度一半；纵向 = 高度 3/4 处
        mid_x = frame_w // 2
        target_y = int(frame_h * DISK_TARGET_Y_RATIO)

        # 识别指定颜色物体
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = get_mask(hsv, ranges)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid = [c for c in contours if cv2.contourArea(c) >= DISK_MIN_AREA]

        if not valid:
            # 没找到目标，清零，继续找
            still_cnt = 0
            prev_cx = None
            prev_cy = None
            continue

        # 取最大轮廓，算中心点
        max_c = max(valid, key=cv2.contourArea)
        M = cv2.moments(max_c)
        if M["m00"] == 0:
            still_cnt = 0
            continue
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        # 条件1：中心点落在指定区域（左右离中线±20，纵向在3/4附近±容差）
        in_region = (abs(cx - mid_x) <= DISK_CENTER_X_TOL) and (abs(cy - target_y) <= DISK_Y_TOL)

        if in_region:
            # 条件2：和上一帧比，中心点几乎没动
            if prev_cx is not None and abs(cx - prev_cx) <= DISK_STILL_PIXEL and abs(cy - prev_cy) <= DISK_STILL_PIXEL:
                still_cnt += 1
            else:
                still_cnt = 1   # 刚进入区域，重新计数
        else:
            # 不在区域，清零
            still_cnt = 0

        prev_cx = cx
        prev_cy = cy

        # 连续4帧在区域内且不动 → 发送 ok，结束
        if still_cnt >= DISK_STILL_FRAME:
            send(link, "ok")
            ok_sent = True
            break

    cap.release()
    if ok_sent:
        return "ok"
    else:
        # 超时没满足条件，自己发一条失败，main 不再发送
        send(link, "4_FAIL")
        return "4_FAIL"


def run_task5(link):
    res = find_zone(link)
    return res


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
                elif cmd == "T2":  # 移动中找球并对准
                    # qiu_xy内部自己发送ok2或失败报文，这里不再重复发送
                    run_task2(link)
                elif cmd == "T3":  # 找桶
                    res = run_task3(link)
                    send(link, res)
                elif cmd == "T4":
                    # T4 由 run_task4 内部自己发 ok / 4_FAIL，这里不再重复发送，避免电控收到两条
                    run_task4(link)
                elif cmd == "T5":  # 安置区对准
                    res = run_task5(link)
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



