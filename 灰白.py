# contour_slider_tool.py 修复版
import cv2
import numpy as np

# ===================== 基础配置 =====================
CAMERA_ID = 0
WIDTH = 640
HEIGHT = 480

# 默认滑条初始值
H_MIN = 0
H_MAX = 179
S_MIN = 0
S_MAX = 255
V_MIN = 0
V_MAX = 255
AREA_MIN = 50
AREA_MAX = 30000

def callback(x):
    pass


if __name__ == "__main__":
    win_name = "轮廓调参工具 | q退出 s保存参数"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1100, 600)

    cv2.createTrackbar("H min", win_name, H_MIN, 179, callback)
    cv2.createTrackbar("H max", win_name, H_MAX, 179, callback)
    cv2.createTrackbar("S min", win_name, S_MIN, 255, callback)
    cv2.createTrackbar("S max", win_name, S_MAX, 255, callback)
    cv2.createTrackbar("V min", win_name, V_MIN, 255, callback)
    cv2.createTrackbar("V max", win_name, V_MAX, 255, callback)
    cv2.createTrackbar("最小面积", win_name, AREA_MIN, 5000, callback)
    cv2.createTrackbar("最大面积", win_name, AREA_MAX, 50000, callback)

    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

    if not cap.isOpened():
        print("摄像头打开失败！检查摄像头编号")
        exit()

    while True:
        h_min = cv2.getTrackbarPos("H min", win_name)
        h_max = cv2.getTrackbarPos("H max", win_name)
        s_min = cv2.getTrackbarPos("S min", win_name)
        s_max = cv2.getTrackbarPos("S max", win_name)
        v_min = cv2.getTrackbarPos("V min", win_name)
        v_max = cv2.getTrackbarPos("V max", win_name)
        area_min = cv2.getTrackbarPos("最小面积", win_name)
        area_max = cv2.getTrackbarPos("最大面积", win_name)

        if h_min > h_max:
            h_min, h_max = h_max, h_min
        if s_min > s_max:
            s_min, s_max = s_max, s_min
        if v_min > v_max:
            v_min, v_max = v_max, v_min
        if area_min > area_max:
            area_min, area_max = area_max, area_min

        ret, frame = cap.read()
        if not ret:
            continue

        blur = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv_img = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)

        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(hsv_img, lower, upper)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        draw_img = frame.copy()
        find_count = 0
        cx = 0
        cy = 0

        if len(contours) > 0:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area_min <= area <= area_max:
                    find_count += 1
                    cv2.drawContours(draw_img, [cnt], -1, (0, 255, 0), 2)
                    M = cv2.moments(cnt)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        cv2.circle(draw_img, (cx, cy), 6, (0, 0, 255), -1)
                        cv2.putText(draw_img, f"({cx},{cy})",
                                    (cx + 8, cy - 8),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    break

        cv2.putText(draw_img, f"检测目标数量:{find_count}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # ==========【重点修复这里】==========
        mask_color = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        combine1 = np.hstack([mask_color, draw_img])
        total = np.hstack([frame, combine1])
        cv2.imshow(win_name, total)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord('s'):
            print("\n【保存当前参数】")
            print(f"H_MIN = {h_min}")
            print(f"H_MAX = {h_max}")
            print(f"S_MIN = {s_min}")
            print(f"S_MAX = {s_max}")
            print(f"V_MIN = {v_min}")
            print(f"V_MAX = {v_max}")
            print(f"AREA_MIN = {area_min}")
            print(f"AREA_MAX = {area_max}")
            print(f"lower = [{h_min},{s_min},{v_min}]")
            print(f"upper = [{h_max},{s_max},{v_max}]")

    cap.release()
    cv2.destroyAllWindows()

    print("\n===== 最终调好轮廓参数 =====")
    print(f"H_MIN = {h_min}")
    print(f"H_MAX = {h_max}")
    print(f"S_MIN = {s_min}")
    print(f"S_MAX = {s_max}")
    print(f"V_MIN = {v_min}")
    print(f"V_MAX = {v_max}")
    print(f"AREA_MIN = {area_min}")
    print(f"AREA_MAX = {area_max}")
    print(f"lower_hsv = [{h_min}, {s_min}, {v_min}]")
    print(f"upper_hsv = [{h_max}, {s_max}, {v_max}]")
    print("cx, cy = 目标中心点坐标")
