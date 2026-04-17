"""PP-OCRv5 engine test - single shot"""
import os, sys, time, json

os.chdir(r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")
sys.path.insert(0, r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")

out = r"d:\grsxbd\test_v5_out.json"

from ppocr_python_engine import PPOCR_python_pipe

pipe = PPOCR_python_pipe(
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_det",
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec",
    argument={"cpu_threads": 4, "det_box_thresh": 0.6},
)

img = r"D:\grsxbd\Umi-OCR\docs\images\Umi-OCR-全局页1.png"
t2 = time.time()
res = pipe.run(img)
t3 = time.time()

pipe.exit()

result = {
    "code": res.get("code"),
    "time": round(t3-t2, 1),
    "lines": len(res["data"]) if res.get("code") == 100 else 0,
    "texts": [l["text"] for l in res["data"][:5]] if res.get("code") == 100 else [],
    "error": str(res.get("data",""))[:100] if res.get("code") != 100 else "",
}

with open(out, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
