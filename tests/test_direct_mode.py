"""
PaddleOCRVL 直接加载模式（绕过 pipeline，无版面分析）
使用 transformers 库直接加载 PaddleOCR-VL 模型
"""
import sys, os
sys.path.insert(0, "D:/grsxbd")
sys.path.insert(0, r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")

os.environ["MKL_THREADING_LAYER"] = "GNU"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import time
from pathlib import Path
from PIL import Image
import numpy as np

TEST_DIR = Path("d:/grsxbd/uploads/debug_regions")
IMAGES = sorted(TEST_DIR.glob("scan_p*.png"))[:10]

print(f"{'='*60}")
print("PaddleOCRVL 直接加载（transformers，无版面分析）")
print(f"{'='*60}")

# 加载模型（直接模式，跳过 pipeline）
t0 = time.time()
print("加载 PaddleOCR-VL 模型（直接模式）...")
from transformers import PaddleOCRVLProcessor, PaddleOCRVLForConditionalGeneration

processor = PaddleOCRVLProcessor.from_pretrained("PaddlePaddle/PaddleOCR-VL-1.5")
model = PaddleOCRVLForConditionalGeneration.from_pretrained("PaddlePaddle/PaddleOCR-VL-1.5")
model.eval()
print(f"加载耗时: {time.time()-t0:.1f}s")

import paddle

def recognize_direct(image_path: str) -> list[str]:
    """直接识别图像中的文字（无需版面分析）"""
    image = Image.open(image_path).convert('RGB')
    inputs = processor(texts=[], images=image, return_tensors="pd")
    with paddle.no_grad():
        generated_ids = model.generate(
            input_ids=inputs['input_ids'],
            image=inputs['image'],
            max_new_tokens=256,
        )
    generated_ids = generated_ids[0].numpy()
    # 解码
    processor_batch = processor._get_processor_batch()
    answer = processor_batch.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return answer if isinstance(answer, list) else [answer]

results = []
for img_path in IMAGES:
    t1 = time.time()
    try:
        texts = recognize_direct(str(img_path))
        elapsed = time.time() - t1
        result_str = " | ".join(str(t)[:20] for t in texts if t)[:60] if texts else "(无文本)"
    except Exception as ex:
        elapsed = time.time() - t1
        result_str = f"错误: {ex}"
        texts = []
    print(f"  {img_path.name}: {elapsed:.1f}s -> {result_str}")
    results.append(elapsed)

avg = sum(results) / len(results)
print(f"\n汇总: 平均 {avg:.2f}s/图, 总计 {sum(results):.1f}s ({len(results)}张)")
print(f"对比 PaddleOCRVL pipeline (含版面): ~9.25s/图")
if avg > 0:
    print(f"速度提升: ~{9.25/avg:.1f}x")
