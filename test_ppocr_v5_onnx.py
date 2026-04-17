"""验证 PP-OCRv5 ONNX 模型是否可通过 Python 子进程加载"""
import subprocess
import sys
import os
import time

python = sys.executable
img_path = r"D:\grsxbd\uploads\pdf\temp_images\page_009.png"
det_model = r"D:\grsxbd\paddle\models\PP-OCRv5_server_det"
rec_model = r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec"
cls_model = r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr\models\ch_ppocr_mobile_v2.0_cls_infer"

code = f'''
import os
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'

from paddleocr import PaddleOCR
import numpy as np

print("初始化 OCR（v5 ONNX 模型）...")
ocr = PaddleOCR(
    det_model_dir=r"{det_model}",
    rec_model_dir=r"{rec_model}",
    use_angle_cls=False,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    lang='ch'
)
print("初始化完成")

img = r"{img_path}"
print(f"预热中: {{img}}")
result = ocr.predict(img)
print(f"预热完成，结果数: {{len(result) if result else 0}}")

# 速度测试
print()
print("===== 速度测试（5次平均）=====")
times = []
for i in range(5):
    start = time.time()
    result = ocr.predict(img)
    elapsed = time.time() - start
    times.append(elapsed)
    print(f"第 {{i+1}} 次: {{elapsed:.2f}}秒")

avg = sum(times) / len(times)
print(f"平均耗时: {{avg:.2f}}秒")
print(f"最快: {{min(times):.2f}}秒")
print(f"最慢: {{max(times):.2f}}秒")

# 输出识别结果
print()
print("===== 识别结果 =====")
if result and result[0]:
    blocks = result[0]
    print(f"识别到 {{len(blocks)}} 个文本块:")
    for block in blocks[:20]:
        if isinstance(block, (list, tuple)) and len(block) >= 2:
            text = block[1][0] if isinstance(block[1], (list, tuple)) else block[1]
            score = block[1][1] if isinstance(block[1], (list, tuple)) and len(block[1]) >= 2 else 0
            print(f"  {{text[:50]}} ({{score:.2f}})")
else:
    print("未识别到文字")
'''

print("===== PP-OCRv5 ONNX 模型加载测试 =====")
print(f"图片: {img_path}")
print(f"检测模型: {det_model}")
print(f"识别模型: {rec_model}")
print(f"分类模型: {cls_model}")
print()

result = subprocess.run(
    [python, '-c', code],
    capture_output=True,
    text=True,
    cwd=os.path.dirname(python),
    timeout=300
)
print(result.stdout)
if result.stderr:
    lines = [l for l in result.stderr.split('\n') if l.strip() and
             'UserWarning' not in l and 'ccache' not in l and
             'Checking' not in l and 'DeprecationWarning' not in l]
    if lines:
        print('\nstderr:')
        print('\n'.join(lines[:50]))
if result.returncode != 0:
    print(f'\n进程返回码: {result.returncode}')
