# -*- coding: utf-8 -*-
"""
PaddleOCR-VL v1.5 完整测试 (CPU)
"""
import sys, os, time, json
from pathlib import Path

sys.path.insert(0, r"D:/grsxbd/.venv_paddleocr/Lib/site-packages")
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import paddleocr
from paddleocr import PaddleOCRVL

OUTPUT_DIR = Path(r"D:/grsxbd/tests/paddle_official_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 加载模型
print("\n" + "=" * 60)
print("PaddleOCR-VL v1.5 CPU 测试")
print("=" * 60)

start = time.time()
vl = PaddleOCRVL(pipeline_version="v1.5", device="cpu")
load_time = time.time() - start
print(f"模型加载: {load_time:.1f}s")

# 预测
img_path = OUTPUT_DIR / "page_003_vl_full.png"
print(f"\n预测图片: {img_path}")
start = time.time()
result = vl.predict(str(img_path))
rec_time = time.time() - start
print(f"识别耗时: {rec_time:.1f}s")

# 提取结果
r = result[0]
res_json = r.json
print(f"\n[INFO] 结果键: {list(res_json.keys())}")

# 获取 layout 检测结果
layout_res = res_json.get("res", {}).get("layout_det_res", {})
boxes = layout_res.get("boxes", [])
print(f"\n检测到 {len(boxes)} 个布局区域:")
for b in boxes:
    label = b.get("label", "?")
    score = b.get("score", 0)
    coord = b.get("coordinate", [])
    print(f"  [{label}] conf:{score:.3f} bbox:{coord}")

# 获取解析结果
parsing = res_json.get("res", {}).get("parsing_res_list", [])
print(f"\n解析出 {len(parsing)} 个文本块:")
for p in parsing:
    label = p.get("block_label", "?")
    content = p.get("block_content", "")
    bbox = p.get("block_bbox", [])
    print(f"  [{label}] bbox:{bbox}")
    print(f"    {content[:100]}")

# 保存完整结果
out = {
    "model": "PaddleOCR-VL v1.5",
    "device": "cpu",
    "load_time_s": round(load_time, 1),
    "rec_time_s": round(rec_time, 1),
    "layout_boxes": boxes,
    "parsing_res": parsing,
}
with open(OUTPUT_DIR / "vl_v15_result.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"\n[OK] 结果已保存: {OUTPUT_DIR / 'vl_v15_result.json'}")
print("完成!")
