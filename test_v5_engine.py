"""验证 PP-OCRv5 Python 引擎 - 结果写入 JSON 文件"""
import os, sys, time, json

os.chdir(r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")
sys.path.insert(0, r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")
from ppocr_python_engine import PPOCR_python_pipe

out_file = r"d:\grsxbd\test_v5_result.json"
results = []

pipe = PPOCR_python_pipe(
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_det",
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec",
    argument={"cpu_threads": 4, "det_box_thresh": 0.6},
)

test_imgs = [
    (r"D:\grsxbd\Umi-OCR\docs\images\Umi-OCR-全局页1.png", "全局页1"),
    (r"D:\grsxbd\Umi-OCR\docs\images\Umi-OCR-截图页1.png", "截图页1"),
]

for img, name in test_imgs:
    t2 = time.time()
    res = pipe.run(img)
    t3 = time.time()
    code = res.get("code")
    entry = {"name": name, "code": code, "time": round(t3-t2, 1)}
    if code == 100:
        lines = res["data"]
        entry["lines"] = len(lines)
        entry["texts"] = [l["text"][:80] for l in lines[:5]]
    else:
        entry["error"] = str(res.get("data", ""))[:100]
    results.append(entry)

pipe.exit()

with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

with open(out_file, "r", encoding="utf-8") as f:
    print(f.read())
