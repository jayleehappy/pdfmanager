import os
# 必须在 paddleocr 导入之前设置
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'

from paddleocr import PaddleOCR
import time

print('初始化模型...')
ocr = PaddleOCR(lang='ch')

img_path = r'D:\grsxbd\uploads\pdf\temp_images\page_009.png'

# 预热
print('预热中...')
result = ocr.ocr(img_path)

# 速度测试
print('\n===== 速度测试（5次平均）=====\n')
times = []
for i in range(5):
    start = time.time()
    result = ocr.ocr(img_path)
    elapsed = time.time() - start
    times.append(elapsed)
    print(f'第 {i+1} 次: {elapsed:.2f}秒')

avg = sum(times) / len(times)
print(f'\n平均耗时: {avg:.2f}秒')
print(f'最快: {min(times):.2f}秒')
print(f'最慢: {max(times):.2f}秒')

# 提取文字
print('\n===== 识别结果 =====\n')
if result and result[0]:
    text = '\n'.join([line[1][0] for line in result[0]])
    print(text)
else:
    print('未识别到文字')
