
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")

# 禁用 PIR 以解决 Windows CPU 兼容性问题
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"

import paddle
paddle.set_flags({"FLAGS_enable_pir_api": False, "FLAGS_enable_pir_in_executor": False})

from paddlex.inference import create_predictor
from paddlex.inference.utils.pp_option import PaddlePredictorOption
import cv2, numpy as np

pp_option = PaddlePredictorOption()
pp_option.device_type = "cpu"
pp_option.run_mode = "paddle"
pp_option.enable_new_ir = False
pp_option.cpu_threads = 4

print("OCR_INIT_OK", flush=True)

# 全局变量
det = None
rec = None

def init_models():
    global det, rec
    print("初始化检测模型...", flush=True)
    det = create_predictor(model_name="PP-OCRv5_server_det", model_dir='D:\\grsxbd\\paddle\\models\\PP-OCRv5_server_det', pp_option=pp_option)
    print("初始化识别模型...", flush=True)
    rec = create_predictor(model_name="PP-OCRv5_server_rec", model_dir='D:\\grsxbd\\paddle\\models\\PP-OCRv5_server_rec', pp_option=pp_option)
    print("模型初始化完成", flush=True)

init_models()

def crop_boxes(img, dt_polys, dt_scores, box_thresh=0.6):
    h, w = img.shape[:2]
    crops, keep_indices = [], []
    for i, (poly, score) in enumerate(zip(dt_polys, dt_scores)):
        if score < box_thresh:
            continue
        pts = poly.astype(np.int64)
        x_min, y_min = int(pts[:, 0].min()), int(pts[:, 1].min())
        x_max, y_max = int(pts[:, 0].max()), int(pts[:, 1].max())
        x_min, y_min = max(0, x_min), max(0, y_min)
        x_max, y_max = min(w, x_max), min(h, y_max)
        if y_max > y_min and x_max > x_min:
            crops.append(img[y_min:y_max, x_min:x_max])
            keep_indices.append(i)
    return crops, keep_indices

def ocr_image(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return {"code": 201, "data": "无法读取图片: " + img_path}

    try:
        # 检测
        det_result = list(det.predict(img))
        dt_polys = det_result[0].get("dt_polys", [])
        dt_scores = det_result[0].get("dt_scores", [])

        if len(dt_polys) == 0:
            return {"code": 101, "data": []}

        # 裁剪
        crops, keep_idx = crop_boxes(img, dt_polys, dt_scores)
        if not crops:
            return {"code": 101, "data": []}

        # 识别（批量）
        rec_results = list(rec.predict(crops))
        texts, scores = [], []
        for res in rec_results:
            texts.append(res.get("rec_text", ""))
            scores.append(res.get("rec_score", 0.0))

        # 合并结果，按 y 坐标排序
        results = []
        for i, (text, score) in enumerate(zip(texts, scores)):
            poly = dt_polys[keep_idx[i]]
            y_min = float(poly[:, 1].min())
            results.append({"text": text, "score": float(score), "y": y_min})
        results.sort(key=lambda x: x["y"])

        return {"code": 100, "data": results}
    except Exception as e:
        import traceback
        return {"code": 500, "data": "OCR错误: " + str(e) + "\n" + traceback.format_exc()}

# 主循环：读取指令并响应
while True:
    try:
        line = sys.stdin.readline()
        if not line:
            break
        req = json.loads(line.strip())
        req_id = req.get("id", 0)
        img_path = req.get("image_path", "")
        result = ocr_image(img_path)
        result["id"] = req_id
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as e:
        err = {"code": 500, "data": str(e), "id": 0}
        try:
            print(json.dumps(err, ensure_ascii=False), flush=True)
        except:
            pass
