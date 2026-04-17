"""PP-OCRv5 with inline debugging"""
import os, sys, time

os.chdir(r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")
sys.path.insert(0, r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")

# 临时 patch _send 添加调试
import ppocr_python_engine as eng
orig_send = eng.PPOCR_python_pipe._send

def debug_send(self, data):
    import uuid, json as json2
    req_id = str(uuid.uuid4())[:8]
    data["id"] = req_id
    if "image_path" in data:
        data["image_path"] = data["image_path"].replace("\\", "/")
    write_str = json2.dumps(data, ensure_ascii=True, indent=None) + "\n"
    print(f"[DEBUG] Sending: {write_str[:100]}", flush=True)
    self._proc.stdin.write(write_str.encode("utf-8"))
    self._proc.stdin.flush()
    print(f"[DEBUG] Sent, waiting for response...", flush=True)

    timeout = 10  # 短超时
    start = time.time()
    while True:
        if time.time() - start > timeout:
            print(f"[DEBUG] Timeout after {timeout}s", flush=True)
            return {"code": 903, "data": "OCR 超时"}
        line = self._proc.stdout.readline()
        print(f"[DEBUG] readline returned: {repr(line[:100])}", flush=True)
        if not line:
            print("[DEBUG] line is empty - process died?", flush=True)
            return {"code": 902, "data": "子进程意外退出"}
        try:
            resp = json2.loads(line.decode("utf-8", errors="replace").strip())
            print(f"[DEBUG] resp id: {resp.get('id')}, req_id: {req_id}", flush=True)
            if resp.get("id") == req_id:
                resp.pop("id", None)
                return resp
        except Exception as e:
            print(f"[DEBUG] JSON parse error: {e}", flush=True)
            continue

eng.PPOCR_python_pipe._send = debug_send

from ppocr_python_engine import PPOCR_python_pipe
import cv2, numpy as np

pipe = PPOCR_python_pipe(
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_det",
    r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec",
    argument={"cpu_threads": 4},
)
print("=== Pipe OK ===")

test_img = r"d:\grsxbd\test_ascii.png"
img = np.full((100, 400, 3), 255, dtype=np.uint8)
cv2.putText(img, "Hello OCR", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
cv2.imwrite(test_img, img)

res = pipe.run(test_img)
print(f"Final: code={res.get('code')}", flush=True)
if res.get("code") == 100:
    print(f"OK: {len(res['data'])} lines", flush=True)
else:
    print(f"FAIL: {str(res)[:200]}", flush=True)

os.remove(test_img)
pipe.exit()
