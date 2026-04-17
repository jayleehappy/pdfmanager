"""PP-OCRv5 完整OCR测试（禁用PIR）"""
import os
import sys
import time
import subprocess

python = sys.executable
img_path = r"D:\grsxbd\uploads\pdf\temp_images\page_009.png"
det_dir = r"D:\grsxbd\paddle\models\PP-OCRv5_server_det"
rec_dir = r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec"
dict_path = r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr\models\dict_chinese.txt"

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

print("初始化模型...")
det = create_predictor(model_name='PP-OCRv5_server_det', model_dir=r"{det_dir}", pp_option=pp_option)
rec = create_predictor(model_name='PP-OCRv5_server_rec', model_dir=r"{rec_dir}", pp_option=pp_option)
print("模型初始化完成")

def crop_boxes(img, dt_polys, dt_scores, box_thresh=0.7):
    """裁剪文本框"""
    h, w = img.shape[:2]
    crops, keep_indices = [], []
    for i, (poly, score) in enumerate(zip(dt_polys, dt_scores)):
        if score < box_thresh:
            continue
        pts = poly.astype(np.int64)
        x_min, y_min = pts[:, 0].min(), pts[:, 1].min()
        x_max, y_max = pts[:, 0].max(), pts[:, 1].max()
        x_min, y_min = max(0, x_min), max(0, y_min)
        x_max, y_max = min(w, x_max), min(h, y_max)
        if y_max > y_min and x_max > x_min:
            crops.append(img[y_min:y_max, x_min:x_max])
            keep_indices.append(i)
    return crops, keep_indices

def ocr(img_path, box_thresh=0.7):
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"无法读取: {{img_path}}")

    # 检测
    det_result = list(det.predict(img))
    dt_polys = det_result[0]["dt_polys"]
    dt_scores = det_result[0]["dt_scores"]
    print(f"  检测到 {{len(dt_polys)}} 个候选框")

    # 裁剪
    crops, keep_idx = crop_boxes(img, dt_polys, dt_scores, box_thresh)
    print(f"  过滤后 {{len(crops)}} 个有效框 (thresh={{box_thresh}})")

    if not crops:
        return []

    # 识别（批量）
    rec_results = list(rec.predict(crops))
    texts, scores = [], []
    for res in rec_results:
        texts.append(res.get("rec_text", ""))
        scores.append(res.get("rec_score", 0.0))

    # 合并结果
    results = []
    for i, (text, score) in enumerate(zip(texts, scores)):
        poly = dt_polys[keep_idx[i]]
        y_min = int(poly[:, 1].min())
        results.append({{"text": text, "score": float(score), "y": y_min}})
    results.sort(key=lambda x: x["y"])
    return results

# 测试
print(f"\\n图片: {{{img_path}}}")
result = ocr(img_path, box_thresh=0.7)
print(f"识别到 {{len(result)}} 个文本行")

# 速度测试（整体OCR）
print("\\n===== OCR速度测试（5次）=====")
times = []
for i in range(5):
    start = time.time()
    result = ocr(img_path, box_thresh=0.7)
    elapsed = time.time() - start
    times.append(elapsed)
    print(f"第 {{i+1}} 次: {{elapsed:.2f}}秒 ({{len(result)}} 行)")

avg = sum(times) / len(times)
print(f"平均: {{avg:.2f}}秒, 最快: {{min(times):.2f}}秒")

print("\\n===== 识别结果 =====")
for i, r in enumerate(result):
    print(f"  {{i+1}}. {{r['text'][:60]}} ({{r['score']:.2f}})")
'''

print("===== PP-OCRv5 完整OCR测试 =====\n")
result = subprocess.run(
    [python, '-c', code],
    capture_output=True,
    text=True,
    timeout=300
)
print(result.stdout)
if result.stderr:
    lines = [l for l in result.stderr.split('\n') if l.strip() and
             'UserWarning' not in l and 'ccache' not in l and
             'Checking' not in l and 'DeprecationWarning' not in l and
             'Logging before' not in l and 'Creating model' not in l and
             '@' not in l and 'global ' not in l and ' WARN' not in l]
    if lines:
        print('\nstderr:')
        print('\n'.join(lines[:20]))
if result.returncode != 0:
    print(f'进程返回码: {{result.returncode}}')
