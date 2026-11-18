# hsv_slider_tool.py
import cv2
import numpy as np

# -------------------------- 摄像头参数 --------------------------
CAMERA_ID = 0
WIDTH = 640
HEIGHT = 480

# 默认初始 HSV 参数（可以自己预设）
H_MIN = 0
H_MAX = 179
S_MIN = 0
S_MAX = 255
V_MIN = 0
V_MAX = 255

# 滑条回调空函数
def callback(x):
    pass

if __name__ == "__main__":
    # 创建窗口
    win_name = "HSV 调参工具 | 按 q 退出"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 900, 600)

    # 创建滑条
    cv2.createTrackbar("H min", win_name, H_MIN, 179, callback)
    cv2.createTrackbar("H max", win_name, H_MAX, 179, callback)
    cv2.createTrackbar("S min", win_name, S_MIN, 255, callback)
    cv2.createTrackbar("S max", win_name, S_MAX, 255, callback)
    cv2.createTrackbar("V min", win_name, V_MIN, 255, callback)
    cv2.createTrackbar("V max", win_name, V_MAX, 255, callback)

    # 打开摄像头
    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

    if not cap.isOpened():
        print("摄像头打开失败！")
        exit()

    while True:
        # 读取滑条当前数值
        h_min = cv2.getTrackbarPos("H min", win_name)
        h_max = cv2.getTrackbarPos("H max", win_name)
        s_min = cv2.getTrackbarPos("S min", win_name)
        s_max = cv2.getTrackbarPos("S max", win_name)
        v_min = cv2.getTrackbarPos("V min", win_name)
        v_max = cv2.getTrackbarPos("V max", win_name)

        # 防止最小值大于最大值（报错）
        if h_min > h_max:
            h_min, h_max = h_max, h_min
        if s_min > s_max:
            s_min, s_max = s_max, s_min
        if v_min > v_max:
            v_min, v_max = v_max, v_min

        # 获取图像
        ret, frame = cap.read()
        if not ret:
            continue

        # 图像预处理（和比赛识别保持一致！）
        blur = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv_img = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)

        # HSV 阈值
        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])

        # 生成掩码
        mask = cv2.inRange(hsv_img, lower, upper)

        # 显示原图 + 遮罩合并查看效果
        res = cv2.bitwise_and(frame, frame, mask=mask)

        # 拼接画面一起看
        top = np.hstack([frame, res])
        cv2.imshow(win_name, top)

        # 按键 q 退出
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    # 释放资源
    cap.release()
    cv2.destroyAllWindows()

    # 退出打印参数，直接复制拿去用
    print("===== 调好的 HSV 参数 =====")
    print(f"H_MIN = {h_min}")
    print(f"H_MAX = {h_max}")
    print(f"S_MIN = {s_min}")
    print(f"S_MAX = {s_max}")
    print(f"V_MIN = {v_min}")
    print(f"V_MAX = {v_max}")
    print(f"lower_hsv = [{h_min}, {s_min}, {v_min}]")
    print(f"upper_hsv = [{h_max}, {s_max}, {v_max}]")
