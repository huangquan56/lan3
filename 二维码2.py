import cv2
import numpy as np
import time
import re

try:
    import zbar          # 板子需先: apt-get install -y python3-zbar
except ImportError:
    zbar = None


QR_ALT_PAT = re.compile(r"^([0-9]+)\+([0-9]+)\+([0-9]+)$")

_zbar_scanner = None     # zbar 解码器（懒加载，全局复用）
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
def _get_scanner():
    global _zbar_scanner
    if _zbar_scanner is None:
        s = zbar.ImageScanner()
        s.parse_config('enable')
        _zbar_scanner = s
    return _zbar_scanner


def _zbar_pts(symbol):
    # zbar 定位点 -> (N,1,2) int32，供 cv2.polylines 画框；拿不到就 None
    try:
        loc = symbol.location
        pts = [(int(x), int(y)) for x, y in loc]
    except Exception:
        return None
    if len(pts) < 4:
        return None
    return np.array(pts, dtype=np.int32).reshape(-1, 1, 2)


def _detect(img):
    # 用 zbar 解码（板子 OpenCV 4.2 未链接 quirc，detectAndDecode 解不出内容）
    # img 可为 BGR 或灰度图；返回 (data, pts)
    if zbar is None:
        raise RuntimeError("缺少 zbar 模块，请在板子上执行: apt-get install -y python3-zbar")
    if img is None:
        return "", None
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = np.ascontiguousarray(gray, dtype=np.uint8)
    h, w = gray.shape[:2]
    try:
        image = zbar.Image(w, h, 'Y800', gray.tobytes())
        _get_scanner().scan(image)
        for symbol in image:
            d = symbol.data
            if isinstance(d, bytes):
                d = d.decode('utf-8', 'ignore')
            return str(d).strip(), _zbar_pts(symbol)
    except Exception:
        return "", None
    return "", None


def try_next(img):    #多重检测
    # 1. 直接用原图
    data, pts = _detect(img)
    if data:
        return data, pts

    h, w = img.shape[:2]
    scale = 1.2
    img_big = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    # 2. 放大后的原图
    data2, pts2 = _detect(img_big)
    if data2:
        return data2, (pts2 / scale if pts2 is not None else None)

    # 3. 增强二值兜底
    bin1 = enhance(img)
    data3, pts3 = _detect(bin1)
    if data3:
        return data3, pts3

    # 4. 反色二值兜底
    img_inv = 255 - img
    bin3 = enhance(img_inv)
    data4, pts4 = _detect(bin3)
    if data4:
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
        data,pts=try_next(frame)
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

