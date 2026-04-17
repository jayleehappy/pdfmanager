"""验证 PP-OCRv5 ONNX 模型 + paddle.set_flags() 禁用 PIR"""
import subprocess
import sys
import os
import time

python = sys.executable
img_path = r"D:\grsxbd\uploads\pdf\temp_images\page_009.png"
det_model = r"D:\grsxbd\paddle\models\PP-OCRv5_server_det"
rec_model = r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec"

code = f'''
import os
# 在任何导入前设置环境变量
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'

import paddle
# 强制禁用 PIR
paddle.set_flags({{
    'FLAGS_enable_pir_api': False,
    'FLAGS_enable_pir_in_executor': False,
}})

from paddleocr import PaddleOCR
import time

print("初始化 OCR...")
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

# 预热
print("预热中...")
result = ocr.predict(img)
print(f"预热完成，结果数: {{len(result) if result else 0}}")

# 速度测试
print()
print("===== 速度测试（5次）=====")
times = []
for i in range(5):
    start = time.time()
    result = ocr.predict(img)
    elapsed = time.time() - start
    times.append(elapsed)
    print(f"第 {{i+1}} 次: {{elapsed:.2f}}秒")

avg = sum(times) / len(times)
print(f"平均: {{avg:.2f}}秒, 最快: {{min(times):.2f}}秒")

# 结果
print()
print("===== 识别结果 =====")
if result and result[0]:
    blocks = result[0]
    print(f"识别到 {{len(blocks)}} 个文本块:")
    for block in blocks[:10]:
        if isinstance(block, (list, tuple)) and len(block) >= 2:
            text = block[1][0] if isinstance(block[1], (list, tuple)) else block[1]
            score = block[1][1] if isinstance(block[1], (list, tuple)) and len(block[1]) >= 2 else 0
            print(f"  {{text[:60]}} ({{score:.2f}})")
else:
    print("未识别到文字")
'''

print("===== PP-OCRv5 + set_flags() PIR 测试 =====")
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
             'Checking' not in l and 'DeprecationWarning' not in l and
             'Logging before' not in l]
    if lines:
        print('\nstderr:')
        print('\n'.join(lines[:30]))
