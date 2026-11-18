# shape_detect_slider.py
import cv2
import numpy as np

# ===================== 基础配置 =====================
CAMERA_ID = 0
WIDTH = 640
HEIGHT = 480

# 面积初始值（滑条默认位置）
AREA_MIN_INIT = 100
AREA_MAX_INIT = 30000
# 滑条最大值
AREA_MIN_MAX = 5000
AREA_MAX_MAX = 50000
# ==============================================================


def callback(x):
    # 滑条空回调，必须保留
    pass


def get_shape_name(cnt):
    # 根据轮廓顶点数 + 圆度判断形状
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
    num = len(approx)
    area = cv2.contourArea(cnt)

    if num == 3:
        return "三角形"
    elif num == 4:
        x1, y1, w, h = cv2.boundingRect(approx)
        ratio = float(w) / h
        if 0.9 <= ratio <= 1.1:
            return "正方形"
        else:
            return "长方形"
    elif num == 5:
        return "五边形"
    else:
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        if r <= 0:
            return "未知"
        circle_area = np.pi * r * r
        roundness = area / circle_area
        if roundness > 0.75:
            return "圆形"
        else:
            return "不规则"


def find_shape(frame, area_min, area_max):
    # 灰度 → 降噪 → 自适应二值 → 形态学去噪 → 找轮廓
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    binary = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2
    )

    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    draw_img = frame.copy()
    result_list = []

    if len(contours) > 0:
        # 面积从大到小排序
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for cnt in contours:
            area = cv2.contourArea(cnt)

            # 面积过滤（用滑条实时数值）
            if area < area_min or area > area_max:
                continue

            shape_name = get_shape_name(cnt)
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                cx, cy = 0, 0

            # 画轮廓 + 中心点 + 形状文字
            cv2.drawContours(draw_img, [cnt], -1, (0, 255, 0), 2)
            cv2.circle(draw_img, (cx, cy), 5, (0, 0, 255), -1)
            cv2.putText(
                draw_img,
                shape_name,
                (cx + 10, cy - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 0),
                1
            )
            result_list.append([shape_name, cx, cy, int(area)])

    return draw_img, result_list


if __name__ == "__main__":
    win_name = "形状识别 | 滑条调面积 | m输出坐标 q退出"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 900, 600)

    # 创建两条面积滑条
    cv2.createTrackbar("最小面积", win_name, AREA_MIN_INIT, AREA_MIN_MAX, callback)
    cv2.createTrackbar("最大面积", win_name, AREA_MAX_INIT, AREA_MAX_MAX, callback)

    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

    if not cap.isOpened():
        print("摄像头打开失败！")
        exit()

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # 读取滑条当前面积
        area_min = cv2.getTrackbarPos("最小面积", win_name)
        area_max = cv2.getTrackbarPos("最大面积", win_name)

        # 防止最小值 > 最大值
        if area_min > area_max:
            area_min, area_max = area_max, area_min

        out_img, res = find_shape(frame, area_min, area_max)

        key = cv2.waitKey(1) & 0xFF

        # 只有按 m 才打印坐标，平时不刷屏
        if key == ord('m'):
            if len(res) > 0:
                print(f"【M 获取数据】最小面积={area_min} 最大面积={area_max} | {res}")
            else:
                print(f"【M 获取数据】没有检测到物体 | 面积范围 {area_min}~{area_max}")

        # q 退出
        if key == ord('q'):
            break

        # 画面提示
        cv2.putText(
            out_img,
            f"面积:{area_min}~{area_max} | m取坐标 q退出",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            1
        )

        cv2.imshow(win_name, out_img)

    cap.release()
    cv2.destroyAllWindows()
    print("程序结束")
