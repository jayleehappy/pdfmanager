import sys
import time
sys.path.insert(0, r'D:\grsxbd\Umi-OCR_Paddle_v2.1.5\UmiOCR-data\plugins\paddlevl_ocr')
from paddlevl_engine import get_paddle_vl_engine

model_path = r'D:\grsxbd\Umi-OCR_Paddle_v2.1.5\UmiOCR-data\plugins\paddlevl_ocr\PaddleOCR-VL'
engine = get_paddle_vl_engine(model_path=model_path)

img_path = r'D:\grsxbd\uploads\pdf\temp_images\page_009.png'

# 预热（首次推理较慢）
print('预热中...')
engine.recognize(img_path)

# 计时测试
print('\n===== 速度测试（5次平均）=====\n')
times = []
for i in range(5):
    start = time.time()
    result = engine.recognize(img_path)
    elapsed = time.time() - start
    times.append(elapsed)
    print(f'第 {i+1} 次: {elapsed:.2f}秒')

avg = sum(times) / len(times)
print(f'\n平均耗时: {avg:.2f}秒')
print(f'最快: {min(times):.2f}秒')
print(f'最慢: {max(times):.2f}秒')
