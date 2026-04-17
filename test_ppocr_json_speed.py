import subprocess
import time
import os

exe_path = r'D:\grsxbd\Umi-OCR_Paddle_v2.1.5\UmiOCR-data\plugins\win7_x64_PaddleOCR-json\PaddleOCR-json.exe'
img_path = r'D:\grsxbd\uploads\pdf\temp_images\page_009.png'
work_dir = r'D:\grsxbd\Umi-OCR_Paddle_v2.1.5\UmiOCR-data\plugins\win7_x64_PaddleOCR-json'

if not os.path.exists(exe_path):
    print(f'错误: {exe_path} 不存在')
    exit(1)

print('===== PaddleOCR-json 速度测试 =====\n')
print(f'图片: {img_path}\n')

# 预热
print('预热中...')
subprocess.run([exe_path, f'-image_path={img_path}'], cwd=work_dir, capture_output=True)

# 速度测试
print('\n===== 速度测试（5次平均）=====\n')
times = []
for i in range(5):
    start = time.time()
    result = subprocess.run([exe_path, f'-image_path={img_path}'], cwd=work_dir, capture_output=True, text=True)
    elapsed = time.time() - start
    times.append(elapsed)
    print(f'第 {i+1} 次: {elapsed:.2f}秒')

avg = sum(times) / len(times)
print(f'\n平均耗时: {avg:.3f}秒')
print(f'最快: {min(times):.3f}秒')
print(f'最慢: {max(times):.3f}秒')

# 显示结果统计
if result.stdout:
    import json
    try:
        data = json.loads(result.stdout)
        if data.get('code') == 100:
            blocks = data.get('data', [])
            print(f'\n===== 识别结果 =====')
            print(f'识别到 {len(blocks)} 个文本块')
    except:
        pass
