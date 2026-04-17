"""Debug why child process dies"""
import os, sys, time, json

os.chdir(r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")
sys.path.insert(0, r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr")

import subprocess, sys as _sys

PYTHON_EXE = _sys.executable

# 子进程代码 - 添加详细错误处理
SUBPROCESS_CODE = r"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")

# 禁用 PIR
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"

import paddle
paddle.set_flags({"FLAGS_enable_pir_api": False, "FLAGS_enable_pir_in_executor": False})

from paddlex.inference import create_predictor
from paddlex.inference.utils.pp_option import PaddlePredictorOption
import cv2, numpy as np

try:
    pp_option = PaddlePredictorOption()
    pp_option.device_type = "cpu"
    pp_option.run_mode = "paddle"
    pp_option.enable_new_ir = False
    pp_option.cpu_threads = 4

    det = create_predictor(model_name="PP-OCRv5_server_det", model_dir=DET_MODEL_DIR, pp_option=pp_option)
    rec = create_predictor(model_name="PP-OCRv5_server_rec", model_dir=REC_MODEL_DIR, pp_option=pp_option)
    print(json.dumps({"status": "ready"}, ensure_ascii=False), flush=True)
except Exception as e:
    print(json.dumps({"status": "error", "msg": str(e)}, ensure_ascii=False), flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

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
    try:
        data = np.fromfile(img_path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return {"code": 201, "data": "cannot decode: " + img_path}
    except Exception as e:
        return {"code": 201, "data": "load error: " + str(e)}

    try:
        det_result = list(det.predict(img))
        dt_polys = det_result[0].get("dt_polys", [])
        dt_scores = det_result[0].get("dt_scores", [])

        if len(dt_polys) == 0:
            return {"code": 101, "data": []}

        crops, keep_idx = crop_boxes(img, dt_polys, dt_scores)
        if not crops:
            return {"code": 101, "data": []}

        rec_results = list(rec.predict(crops))
        texts, scores = [], []
        for res in rec_results:
            texts.append(res.get("rec_text", ""))
            scores.append(res.get("rec_score", 0.0))

        results = []
        for i, (text, score) in enumerate(zip(texts, scores)):
            poly = dt_polys[keep_idx[i]]
            y_min = float(poly[:, 1].min())
            results.append({"text": text, "score": float(score), "y": y_min})
        results.sort(key=lambda x: x["y"])

        return {"code": 100, "data": results}
    except Exception as e:
        return {"code": 500, "data": "OCR error: " + str(e)}

while True:
    try:
        line = sys.stdin.readline()
        if not line:
            print("# stdin EOF", flush=True)
            break
        req = json.loads(line.strip())
        req_id = req.get("id", 0)
        img_path = req.get("image_path", "")
        print("# processing:", img_path, flush=True)
        result = ocr_image(img_path)
        result["id"] = req_id
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as e:
        import traceback
        print("# EXCEPTION: " + str(e), flush=True)
        traceback.print_exc()
        err = {"code": 500, "data": str(e), "id": 0}
        try:
            print(json.dumps(err, ensure_ascii=False), flush=True)
        except:
            pass
"""

det_dir = r"D:\grsxbd\paddle\models\PP-OCRv5_server_det"
rec_dir = r"D:\grsxbd\paddle\models\PP-OCRv5_server_rec"

code = SUBPROCESS_CODE
code = code.replace("DET_MODEL_DIR", repr(os.path.abspath(det_dir)))
code = code.replace("REC_MODEL_DIR", repr(os.path.abspath(rec_dir)))

startupinfo = None
if sys.platform == "win32":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags = subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

proc = subprocess.Popen(
    [PYTHON_EXE, "-u", "-c", code],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    startupinfo=startupinfo,
    bufsize=0,
)

print("Waiting for ready...")
ready = proc.stdout.readline()
print("Ready:", ready)

# 检查 stderr
import select
stderr_data = b""
# 先检查是否有初始stderr
import time
time.sleep(0.5)
# 非阻塞读取 stderr
import fcntl, os
# 设置为非阻塞
fd = proc.stderr.fileno()
fl = fcntl.fcntl(fd, fcntl.F_GETFL)
fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
try:
    stderr_data = proc.stderr.read()
    if stderr_data:
        print("STDERR:", stderr_data.decode("utf-8", errors="replace"))
except:
    pass

# 发送测试请求
test_img = r"d:\grsxbd\test_ascii.png"
import cv2, numpy as np
img = np.full((100, 400, 3), 255, dtype=np.uint8)
cv2.putText(img, "Hello", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
cv2.imwrite(test_img, img)

data = {"id": "test1", "image_path": test_img.replace("\\", "/")}
write_str = json.dumps(data, ensure_ascii=True) + "\n"
proc.stdin.write(write_str.encode("utf-8"))
proc.stdin.flush()
print("Sent request, waiting 30s...")

start = time.time()
while True:
    if time.time() - start > 30:
        print("TIMEOUT 30s")
        break
    ready_r, _, _ = select.select([proc.stdout], [], [], 1.0)
    if ready_r:
        line = proc.stdout.readline()
        print("Response:", repr(line[:200]))
        break
    else:
        poll = proc.poll()
        if poll is not None:
            print(f"Process died! poll={poll}")
            break
        print(f"still alive... {int(time.time()-start)}s", flush=True)

# 最终读取 stderr
import subprocess as sp2
result = sp2.run(["tasklist", "/FI", "IMAGENAME eq python.exe"], capture_output=True)
print(result.stdout.decode("utf-8", errors="replace"))

proc.kill()
os.remove(test_img)
print("Done")
