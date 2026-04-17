"""PP-OCRv5 debug test"""
import os, sys, time, json, traceback

os.chdir(r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")
sys.path.insert(0, r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")
from ppocr_python_engine import PPOCR_python_pipe

pipe = PPOCR_python_pipe(
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_det",
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec",
    argument={"cpu_threads": 4, "det_box_thresh": 0.6},
)
print("Pipe created OK")

# 用纯ASCII路径测试（创建临时测试图片）
import cv2, numpy as np
test_img = r"d:\grsxbd\test_ascii.png"
# 创建一个简单的测试图片
img = np.full((100, 400, 3), 255, dtype=np.uint8)
cv2.putText(img, "Hello OCR", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
cv2.imwrite(test_img, img)
print(f"Test image created: {test_img}")

# 测试单张
t2 = time.time()
res = pipe.run(test_img)
t3 = time.time()
print(f"Result code: {res.get('code')}, time: {t3-t2:.1f}s")

if res.get("code") == 100:
    print(f"OK: {len(res['data'])} lines")
    for l in res["data"][:3]:
        print(f"  '{l['text']}'")
elif res.get("code") == 500:
    print(f"Error: {res['data'][:200]}")
else:
    print(f"Other: {str(res)[:200]}")

os.remove(test_img)
pipe.exit()
print("Done")
