import subprocess
import time
import os

exe_path = r'D:\grsxbd\Umi-OCR_Paddle_v2.1.5\UmiOCR-data\plugins\win7_x64_PaddleOCR-json\PaddleOCR-json.exe'
img_path = r'D:\grsxbd\uploads\pdf\temp_images\page_009.png'

# 检查 exe 是否存在
if not os.path.exists(exe_path):
    print(f'错误: PaddleOCR-json.exe 不存在: {exe_path}')
    exit(1)

print('===== PaddleOCR-json 速度测试 =====\n')
print(f'图片: {img_path}\n')

# 预热
print('预热中...')
subprocess.run([exe_path, '-image_path=' + img_path, '-r=true'], capture_output=True)

# 速度测试
print('\n===== 速度测试（5次平均）=====\n')
times = []
for i in range(5):
    start = time.time()
    result = subprocess.run([exe_path, '-image_path=' + img_path, '-r=true'], capture_output=True, text=True)
    elapsed = time.time() - start
    times.append(elapsed)
    print(f'第 {i+1} 次: {elapsed:.2f}秒')

avg = sum(times) / len(times)
print(f'\n平均耗时: {avg:.2f}秒')
print(f'最快: {min(times):.2f}秒')
print(f'最慢: {max(times):.2f}秒')

# 显示结果
print('\n===== 识别结果 =====\n')
if result.stdout:
    print(result.stdout[:3000])
else:
    print('无输出')
    print('stderr:', result.stderr[:500])
