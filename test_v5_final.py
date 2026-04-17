"""PP-OCRv5 final integration test"""
import os, sys, time, json

os.chdir(r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")
sys.path.insert(0, r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")
from ppocr_python_engine import PPOCR_python_pipe

pipe = PPOCR_python_pipe(
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_det",
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec",
    argument={"cpu_threads": 4, "det_box_thresh": 0.6},
)

results = []
test_imgs = [
    (r"D:\grsxbd\Umi-OCR\docs\images\Umi-OCR-全局页1.png", "global_page"),
    (r"D:\grsxbd\Umi-OCR\docs\images\Umi-OCR-截图页1.png", "screenshot_page"),
]

for img_path, name in test_imgs:
    t0 = time.time()
    res = pipe.run(img_path)
    t1 = time.time()
    entry = {
        "name": name,
        "code": res.get("code"),
        "ocr_time_s": round(t1-t0, 1),
    }
    if res.get("code") == 100:
        lines = res["data"]
        entry["lines"] = len(lines)
        entry["texts"] = [l["text"] for l in lines[:5]]
    else:
        entry["error"] = str(res.get("data", ""))[:200]
    results.append(entry)

pipe.exit()

out_file = r"d:\grsxbd\test_v5_integration.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# Read back
with open(out_file, "r", encoding="utf-8") as f:
    print(f.read())
