import cv2
import numpy as np

def get_color(event, x, y, flags, data):
    if event == cv2.EVENT_LBUTTONDOWN:
        b,g,r=img[y,x]
        print(b,g,r)
        print(x,y)

if __name__=='__main__':
    img = cv2.imread('shape.png',cv2.IMREAD_COLOR)
    if img is None:
        print('fail')
        exit(0)
    cv2.namedWindow('取色')
    cv2.setMouseCallback("取色",get_color)
    while True:
        cv2.imshow("取色",img)
        k = cv2.waitKey(1) & 0xFF
        if k == 27:
            break
    cv2.destroyAllWindows()








