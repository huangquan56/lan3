# 扫码预览.py —— 泰山派上运行，电脑浏览器实时看二维码识别结果
# 逻辑复用 二维码2.py 的 try_next / parse_QR / is_ok_qr，不重复实现
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

from 二维码2 import try_next, parse_QR, is_ok_qr

VIDEO_INDEX = 10                # ← USB 摄像头号（video9 已消失，实测 10 为摄像头）
STABLE_THRESHOLD = 3            # 连续 N 帧同一结果才认定

cap = cv2.VideoCapture(VIDEO_INDEX, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
print("camera opened:", cap.isOpened())
lock = threading.Lock()

last_data = ""
stable_frame = 0
result = None                   # 最近一次解析成功的 (a, b, c)

HTML = b'<html><body style="margin:0;background:#111"><img src="/stream" style="width:100%"></body></html>'


def gen_frames():
    global last_data, stable_frame, result
    while True:
        with lock:
            ok, frame = cap.read()
        if not ok:
            print("read failed")
            time.sleep(0.1)
            continue

        try:
            data, pts = try_next(frame)      # try_next 返回 2 个值
        except Exception:                    # zbar 未安装/偶发异常时跳过这一帧
            data, pts = "", None

        if data != "":
            if data == last_data:
                stable_frame += 1
            else:
                stable_frame = 0
                last_data = data
        else:
            stable_frame = 0

        if pts is not None:
            cv2.polylines(frame, [pts.astype(np.int32)], True, (0, 255, 0), 2)

        if stable_frame >= STABLE_THRESHOLD and is_ok_qr(data):
            res = parse_QR(data)
            if res is not None:
                result = res

        # 把状态叠在画面上，浏览器里直接能看
        cv2.putText(frame, f"raw={data}", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, f"stable={stable_frame}", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        if result is not None:
            a, b, c = result
            cv2.putText(frame, f"paobao={a}  jiuyuan={b}  anzhiqu={c}",
                        (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            continue
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(HTML)
            elif self.path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type",
                                 "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                for chunk in gen_frames():
                    self.wfile.write(chunk)
        except Exception as e:
            print("ERR:", e)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("浏览器打开: http://192.168.137.100:8000")
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
