import cv2
import numpy as np

def nothing(x):
    pass

cv2.namedWindow("img")
# 创建 HSV 六个滑块（专门用来抠红球）
cv2.createTrackbar("H_min", "img", 0, 179, nothing)
cv2.createTrackbar("H_max", "img", 10, 179, nothing)
cv2.createTrackbar("S_min", "img", 80, 255, nothing)
cv2.createTrackbar("S_max", "img", 255, 255, nothing)
cv2.createTrackbar("V_min", "img", 80, 255, nothing)
cv2.createTrackbar("V_max", "img", 255, 255, nothing)

# ========== 这里换成你的图片 ==========
# 如果图片和 py 文件放同一文件夹，直接写文件名
src_img = cv2.imread("shapes.jpg", cv2.IMREAD_COLOR)
if src_img is None:
    print("图片读取失败！检查文件名、后缀、路径")
    exit()

while True:
    h_min = cv2.getTrackbarPos("H_min", "img")
    h_max = cv2.getTrackbarPos("H_max", "img")
    s_min = cv2.getTrackbarPos("S_min", "img")
    s_max = cv2.getTrackbarPos("S_max", "img")
    v_min = cv2.getTrackbarPos("V_min", "img")
    v_max = cv2.getTrackbarPos("V_max", "img")

    hsv = cv2.cvtColor(src_img, cv2.COLOR_BGR2HSV)
    lower = np.array([h_min, s_min, v_min])
    upper = np.array([h_max, s_max, v_max])
    mask = cv2.inRange(hsv, lower, upper)

    # 把原图 + 掩码一起显示
    result = cv2.bitwise_and(src_img, src_img, mask=mask)
    cv2.imshow("img", result)

    key = cv2.waitKey(1)
    if key == ord('q'):
        break

cv2.destroyAllWindows()
