import cv2
import numpy as np
import time
import re


QR_ALT_PAT = re.compile(r"^([0-9]+)\+([0-9]+)\+([0-9]+)$")

detector=cv2.QRCodeDetector()#3帧检测
last_data=''
stable_frame=0
STABLE_THRESHOLD=3

TASK_a=None
TASK_b=None
TASK_c=None
def parse_QR(qr):            #拿到文本后类型判断
    global TASK_a,TASK_b,TASK_c
    if isinstance(qr, list):
        if len(qr)>0:
            qr=str(qr[0])
        else:
            return None
    if not isinstance(qr, str):
        return None

    s=qr.strip()
    match=QR_ALT_PAT.match(s)
    if match:
        a=int(match.group(1))
        b=int(match.group(2))
        c=int(match.group(3))
        TASK_a,TASK_b,TASK_c=a,b,c
        return (a,b,c)
    else:
        return None
def is_ok_qr(text):         #解码立即校验
    if isinstance(text,list):
        if len(text)>0:
            text=str(text[0])
        else:
            return False
    if not isinstance(text,str):
        return False
    t=text.strip()
    if QR_ALT_PAT.match(t):
        return True
    return False


def enhance(img):    #强化图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray=cv2.equalizeHist(gray)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    binary=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,blockSize=21,C=4)
    # _,binary = cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    return binary
def _detect(img):
    # 兼容不同 cv2 版本：detectAndDecode 可能返回 2 个值(retval,points)或 3 个值(+straight_qrcode)
    r = detector.detectAndDecode(img)
    if len(r) == 2:
        return r[0], r[1], None
    return r[0], r[1], r[2]


def try_next(img):    #多重检测
    # 1. 直接用原图
    data, pts, _ = _detect(img)
    if data and pts is not None:
        return data, pts

    h, w = img.shape[:2]
    scale = 1.2
    img_big = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    # 2. 放大后的原图
    data2, pts2, _ = _detect(img_big)
    if data2 and pts2 is not None:
        return data2, pts2 / scale

    # 3. 增强二值兜底
    bin1 = enhance(img)
    data3, pts3, _ = _detect(bin1)
    if data3 and pts3 is not None:
        return data3, pts3

    # 4. 反色二值兜底
    img_inv = 255 - img
    bin3 = enhance(img_inv)
    data4, pts4, _ = _detect(bin3)
    if data4 and pts4 is not None:
        return data4, pts4

    return "", None


def read_QR_one(timeout_sec=8):                      #对外调用
    global last_data,stable_frame,TASK_a,TASK_b,TASK_c
    TASK_a=None
    TASK_b=None
    TASK_c=None
    last_data=''
    stable_frame=0
    cap=cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
    start=time.time()
    while time.time()-start<timeout_sec:
        ret,frame=cap.read()
        if not ret:
            cv2.waitKey(1)
            continue
        data,pts,_=try_next(frame)
        if data!="":
            if data==last_data:
                stable_frame+=1
            else:
                stable_frame=0
                last_data=data
        else:
            stable_frame=0
        if stable_frame>=STABLE_THRESHOLD:
            if is_ok_qr(data):
                res = parse_QR(data)
                if res is not None:
                    cap.release()
                    return True
            stable_frame = 0
            cv2.waitKey(1)
    cap.release()
    return False


if __name__=="__main__":         #调试
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        data, pts, = try_next(frame)
        if data != "":
            if data == last_data:
                stable_frame += 1
            else:
                stable_frame = 0
                last_data = data
        else:
            stable_frame = 0

        if pts is not None:
            pts = pts.astype(np.int32)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
        if stable_frame >= STABLE_THRESHOLD:
            print(f"原始数据{data}")
            res = parse_QR(data)
            if res is not None:
                a, b, c = res
                print(f"排爆{a},救援{b},安置{c}")
            else:
                print(f"无法解析{data}")
            stable_frame = 0

        cv2.putText(frame, str(stable_frame), (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        if TASK_a is not None and TASK_b is not None and TASK_c is not None:
            text = f"{TASK_a},{TASK_b},{TASK_c}"
            cv2.putText(frame, text, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow('frame', frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

