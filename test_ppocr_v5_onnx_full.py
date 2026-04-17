"""PP-OCRv5 ONNX OCR 完整管道（ONNX Runtime + OpenCV，无 PaddlePaddle）"""
import os
import sys
import time
import json
import numpy as np
import cv2
import onnxruntime as ort

# ============ 配置 ============
DET_MODEL = r"D:\grsxbd\paddle\models\PP-OCRv5_server_det\inference.onnx"
REC_MODEL = r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec\inference.onnx"
IMG_PATH = r"D:\grsxbd\uploads\pdf\temp_images\page_009.png"
DICT_PATH = r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr\models\dict_chinese.txt"

# 检测参数（来自 inference.yml）
DET_RESIZE_LONG = 960
DET_THESH = 0.3
DET_BOX_THESH = 0.6
DET_UNCLIP_RATIO = 1.5
DET_MAX_CANDIDATES = 1000

# 识别参数
REC_HEIGHT = 48
REC_WIDTH = 320

# ============ 字典加载 ============
def load_dict(dict_path):
    with open(dict_path, 'r', encoding='utf-8') as f:
        chars = [line.strip() for line in f]
    return chars

# ============ 检测预处理 ============
def det_preprocess(img, max_side_len=960):
    """预处理图片用于检测：resize 到固定长边，padding"""
    h, w = img.shape[:2]
    scale = max_side_len / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(img, (new_w, new_h))

    # 归一化 (BGR → normalize with mean/std)
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    normalized = (resized.astype(np.float32) / 255.0 - mean) / std

    # HWC → CHW
    transposed = normalized.transpose(2, 0, 1).astype(np.float32)
    return transposed, scale, (h, w)

# ============ 检测后处理 (DB) ============
def unclip(box, unclip_ratio=1.5):
    """扩展多边形"""
    perimeter = cv2.arcLength(box.astype(np.float32), True)
    area = cv2.contourArea(box.astype(np.float32), True)
    if area <= 0:
        return box
    distance = perimeter * unclip_ratio / 2.0
    return cv2.approxPolyDP(box.astype(np.float32), 0.4 * unclip_ratio, True)

def detect_postprocess(seg_map, scale, orig_shape, thresh=0.3, box_thresh=0.6,
                       unclip_ratio=1.5, max_candidates=1000):
    """DB后处理：从分割图提取多边形"""
    h_orig, w_orig = orig_shape
    seg_map = seg_map[0]  # [1, H, W] → [H, W]

    # 阈值化
    binary = (seg_map > thresh).astype(np.uint8)

    # 找到轮廓
    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for contour in contours[:max_candidates]:
        area = cv2.contourArea(contour)
        if area < 10:
            continue

        # 扩展多边形
        expanded = unclip(contour, unclip_ratio)
        expanded = expanded.astype(np.int64)

        # 计算面积
        expanded_area = cv2.contourArea(expanded)
        if expanded_area <= 0:
            continue

        # 过滤太小的 box
        if len(expanded) < 4:
            continue

        # 计算得分（取 contour 区域的平均分割值）
        mask = np.zeros(binary.shape, dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 1, -1)
        score = float(seg_map[mask > 0].mean())
        if score < box_thresh:
            continue

        # 缩放到原图坐标
        boxes.append({
            'polygon': (expanded / 4).tolist(),  # DB输出是1/4尺寸
            'score': score
        })

    return boxes

# ============ 识别预处理 ============
def rec_preprocess(crops):
    """预处理文字块用于识别：归一化 + resize"""
    mean = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    std = np.array([0.5, 0.5, 0.5], dtype=np.float32)

    batch = []
    widths = []
    for crop in crops:
        h, w = crop.shape[:2]
        # 保持宽高比 resize 到 48px 高
        new_w = max(int(w * REC_HEIGHT / h), 16)
        new_w = min(new_w, REC_WIDTH)
        resized = cv2.resize(crop, (new_w, REC_HEIGHT))
        widths.append(new_w)

        # 归一化
        normalized = (resized.astype(np.float32) / 255.0 - mean) / std
        # HWC → CHW
        transposed = normalized.transpose(2, 0, 1).astype(np.float32)
        batch.append(transposed)

    # Padding 到 REC_WIDTH
    max_w = REC_WIDTH
    batched = np.zeros((len(batch), 3, REC_HEIGHT, max_w), dtype=np.float32)
    for i, (t, w) in enumerate(zip(batch, widths)):
        batched[i, :, :, :w] = t

    return batched

# ============ CTC 解码 ============
def ctc_decode(preds, chars, blank=0):
    """CTC greedy decode"""
    results = []
    for pred in preds:
        # pred: [seq_len, num_chars]
        indices = np.argmax(pred, axis=-1)
        # CTC collapse
        text = []
        prev = -1
        for idx in indices:
            if idx != prev and idx != blank:
                if idx < len(chars):
                    text.append(chars[idx])
            prev = idx
        results.append(''.join(text))
    return results

# ============ 完整 OCR 管道 ============
class PPOCRV5ONNX:
    def __init__(self, det_model, rec_model, dict_path):
        print("加载检测模型...")
        self.det_sess = ort.InferenceSession(det_model, providers=['CPUExecutionProvider'])
        print("加载识别模型...")
        self.rec_sess = ort.InferenceSession(rec_model, providers=['CPUExecutionProvider'])
        print("加载字典...")
        self.chars = load_dict(dict_path)
        print(f"字典大小: {len(self.chars)}")

    def detect(self, img):
        preprocessed, scale, orig_shape = det_preprocess(img, DET_RESIZE_LONG)
        # 添加 batch 维度
        preprocessed = preprocessed[np.newaxis, :]
        outputs = self.det_sess.run(None, {'x': preprocessed})
        seg_map = outputs[0][0]  # [1, H, W] → [H, W]
        boxes = detect_postprocess(seg_map, scale, orig_shape,
                                   thresh=DET_THESH, box_thresh=DET_BOX_THESH,
                                   unclip_ratio=DET_UNCLIP_RATIO,
                                   max_candidates=DET_MAX_CANDIDATES)
        return boxes

    def recognize(self, img, boxes):
        if not boxes:
            return []

        # 裁剪文字块
        h, w = img.shape[:2]
        crops = []
        for box_info in boxes:
            polygon = np.array(box_info['polygon'])
            # 简单的 4 点变换
            try:
                rect = cv2.minAreaRect(polygon)
                box = cv2.boxPoints(rect)
                box = np.int64(box)
                # 裁剪
                x, y, cw, ch = cv2.boundingRect(box)
                x, y = max(0, x), max(0, y)
                x2, y2 = min(w, x + cw), min(h, y + ch)
                if x2 > x and y2 > y:
                    crop = img[y:y2, x:x2]
                    crops.append(crop)
                else:
                    crops.append(np.zeros((20, 20, 3), dtype=np.uint8))
            except:
                crops.append(np.zeros((20, 20, 3), dtype=np.uint8))

        if not crops:
            return []

        # 识别
        preprocessed = rec_preprocess(crops)
        outputs = self.rec_sess.run(None, {'x': preprocessed})
        preds = outputs[0]  # [batch, seq_len, num_chars]
        texts = ctc_decode(preds, self.chars)

        results = []
        for box, text in zip(boxes, texts):
            results.append({
                'text': text,
                'score': float(box['score']),
                'polygon': box['polygon']
            })
        return results

    def ocr(self, img_path):
        img = cv2.imread(str(img_path))
        if img is None:
            raise ValueError(f"无法读取图片: {img_path}")
        boxes = self.detect(img)
        results = self.recognize(img, boxes)
        return results

# ============ 主程序 ============
if __name__ == '__main__':
    print("===== PP-OCRv5 ONNX 完整管道测试 =====\n")

    ocr = PPOCRV5ONNX(DET_MODEL, REC_MODEL, DICT_PATH)

    print("\n预热中...")
    result = ocr.ocr(IMG_PATH)
    print(f"预热完成，识别到 {len(result)} 个文本块")

    print("\n===== 速度测试（5次）=====")
    times = []
    for i in range(5):
        start = time.time()
        result = ocr.ocr(IMG_PATH)
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"第 {i+1} 次: {elapsed:.2f}秒")

    avg = sum(times) / len(times)
    print(f"平均: {avg:.2f}秒, 最快: {min(times):.2f}秒")

    print("\n===== 识别结果（前20个）=====")
    for i, r in enumerate(result[:20]):
        print(f"  [{i+1}] {r['text'][:50]} (得分:{r['score']:.2f})")
    if len(result) > 20:
        print(f"  ... 共 {len(result)} 个文本块")
