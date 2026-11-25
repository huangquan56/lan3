# 二维码预览.py —— 泰山派上运行，电脑浏览器实时看二维码检测结果
# 用法：python3 二维码预览.py   然后浏览器打开 http://<板子IP>:8001
import os, sys, threading, importlib.util, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cv2
import numpy as np

VIDEO_INDEX = 9          # ← USB 摄像头号，按 ls /dev/video* 的结果改
PORT = 8001              # 避开 111.py 用的 8000
STABLE_THRESHOLD = 3     # 连续几帧解出同样的内容才算稳定
BOARD_IP = "192.168.137.100"

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qr", os.path.join(HERE, "二维码2.py"))
qr = importlib.util.module_from_spec(spec)
sys.modules["qr"] = qr
spec.loader.exec_module(qr)

cap = cv2.VideoCapture(VIDEO_INDEX, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
print("camera opened:", cap.isOpened())
lock = threading.Lock()

HTML = b'<html><body style="margin:0;background:#111"><img src="/stream" style="width:100%"></body></html>'


def gen_frames():
    last_data = ""
    stable = 0
    while True:
        with lock:
            ok, frame = cap.read()
        if not ok:
            print("read failed")
            time.sleep(0.1)
            continue

        try:
            data, pts = qr.try_next(frame)
        except cv2.error:            # OpenCV 4.2 偶发异常，兜住不中断推流
            data, pts = "", None

        if data != "":
            if data == last_data:
                stable += 1
            else:
                stable = 0
                last_data = data
        else:
            stable = 0

        # 画出二维码检测框
        if pts is not None:
            cv2.polylines(frame, [pts.astype(np.int32)], True, (0, 255, 0), 2)

        cv2.putText(frame, "stable=%d" % stable, (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        if data:
            cv2.putText(frame, "raw=%s" % data, (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        if stable >= STABLE_THRESHOLD:
            ok_qr = qr.is_ok_qr(data)
            res = qr.parse_QR(data)
            color = (0, 255, 0) if res else (0, 0, 255)
            cv2.putText(frame, "ok=%s res=%s" % (ok_qr, res), (20, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

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
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                for chunk in gen_frames():
                    self.wfile.write(chunk)
        except Exception as e:
            print("ERR:", e)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("浏览器打开: http://%s:%d" % (BOARD_IP, PORT))
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
