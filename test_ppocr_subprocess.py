import os
import subprocess
import sys
import json
import time

python = sys.executable
code = '''
import os
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'

from paddleocr import PaddleOCR
import numpy as np
from pdf2image import convert_from_path

ocr = PaddleOCR(lang='ch')
images = convert_from_path('D:/grsxbd/uploads/pdf/temp_split/page_002.pdf', dpi=200)

# 预热
ocr.predict(np.array(images[0]))

# 速度测试
import time
times = []
for i in range(5):
    start = time.time()
    result = ocr.predict(np.array(images[0]))
    elapsed = time.time() - start
    times.append(elapsed)
    print(f'第 {i+1} 次: {elapsed:.2f}秒')

import statistics
print(f'平均: {statistics.mean(times):.2f}秒, 最快: {min(times):.2f}秒')

# 输出识别结果
result = ocr.predict(np.array(images[0]))
if result and result[0]:
    text = '\\n'.join([line[1][0] for line in result[0]])
    print('===== 结果 =====')
    print(text)
'''

result = subprocess.run(
    [python, '-c', code],
    capture_output=True,
    text=True,
    cwd=os.path.dirname(python)
)
print(result.stdout)
if result.stderr:
    # 过滤警告
    lines = [l for l in result.stderr.split('\n') if l.strip() and 'UserWarning' not in l and 'ccache' not in l and 'Checking' not in l and 'DeprecationWarning' not in l]
    if lines:
        print('\nstderr:')
        print('\n'.join(lines[:30]))
