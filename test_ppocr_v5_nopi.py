"""PP-OCRv5 完整OCR测试（禁用PIR，使用paddle模式）"""
import os
import sys
import time
import subprocess
import numpy as np

python = sys.executable
img_path = r"D:\grsxbd\uploads\pdf\temp_images\page_009.png"
det_dir = r"D:\grsxbd\paddle\models\PP-OCRv5_server_det"
rec_dir = r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec"

code = f'''
import os
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'

import paddle
paddle.set_flags({{'FLAGS_enable_pir_api': False, 'FLAGS_enable_pir_in_executor': False}})

from paddlex.inference import create_predictor
from paddlex.inference.utils.pp_option import PaddlePredictorOption
import cv2, time, numpy as np

pp_option = PaddlePredictorOption()
pp_option.device_type = 'cpu'
pp_option.run_mode = 'paddle'
pp_option.enable_new_ir = False
pp_option.cpu_threads = 4

print("创建检测模型...")
det_model = create_predictor(model_name='PP-OCRv5_server_det', model_dir=r"{det_dir}", pp_option=pp_option)
print("创建识别模型...")
rec_model = create_predictor(model_name='PP-OCRv5_server_rec', model_dir=r"{rec_dir}", pp_option=pp_option)
print("模型初始化完成")

img = cv2.imread(r"{img_path}")
print(f"图片尺寸: {{img.shape}}")

# 检测
det_input = det_model.get_input_handle("x")
det_output = det_model.get_output_handle("fetch_name_0")
print(f"检测输出shape: {{det_output.shape()}}")

# 速度测试
print()
print("===== 检测速度测试（5次）=====")
times = []
test_input = np.random.randn(1, 3, 640, 640).astype(np.float32)
for i in range(5):
    start = time.time()
    det_input.copy_from_cpu(test_input)
    det_model.run()
    result = det_output.copy_to_cpu()
    elapsed = time.time() - start
    times.append(elapsed)
    print(f"第 {{i+1}} 次: {{elapsed:.2f}}秒")

avg = sum(times) / len(times)
print(f"平均: {{avg:.2f}}秒, 最快: {{min(times):.2f}}秒")
print("测试完成！")
'''

print("===== PP-OCRv5 禁用PIR推理测试 =====\n")
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
             'Logging before' not in l and 'Creating model' not in l]
    if lines:
        print('\nstderr:')
        print('\n'.join(lines[:30]))
