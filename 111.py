# web.py —— 泰山派上运行，电脑浏览器实时看画面+遮罩
import os, sys, threading, importlib.util, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cv2
import numpy as np

VIDEO_INDEX = 9                 # ← 你的 USB 摄像头号
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ball", os.path.join(HERE, "小球2 .py"))
ball = importlib.util.module_from_spec(spec); sys.modules["ball"] = ball
spec.loader.exec_module(ball)

MODE, IDX = "zone", 2           # 想预览哪张表 / 哪个编号（ball/rescue/zone）
MAPS = {"ball": ball.COLOR_MAP, "rescue": ball.COLOR_MAP2, "zone": ball.ZONE_MAP}
_r = MAPS[MODE][IDX]
RANGES = [_r] if isinstance(_r, tuple) else _r

cap = cv2.VideoCapture(VIDEO_INDEX, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))  # UVC 常用，读不到帧时很关键
print("camera opened:", cap.isOpened())
lock = threading.Lock()

HTML = b'<html><body style="margin:0;background:#111"><img src="/stream" style="width:100%"></body></html>'

def gen_frames():
    while True:
        with lock:
            ok, frame = cap.read()
        if not ok:
            print("read failed")
            time.sleep(0.1)
            continue
        mask = ball.get_mask(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV), RANGES)
        vis = cv2.addWeighted(frame, 0.6, cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR), 0.4, 0)
        mid = frame.shape[1] // 2
        cv2.line(vis, (mid, 0), (mid, frame.shape[0]), (0, 0, 255), 1)
        both = np.hstack([frame, vis])
        ok, buf = cv2.imencode(".jpg", both, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            continue
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == "/":
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
                self.wfile.write(HTML)
            elif self.path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                for chunk in gen_frames():
                    self.wfile.write(chunk)
        except Exception as e:
            print("ERR:", e)          # 关键：不再吞异常
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    print("浏览器打开: http://192.168.137.100:8000")
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
