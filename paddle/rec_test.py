import numpy as np, onnxruntime as ort, cv2, yaml, os, sys
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
sys.stdout.reconfigure(encoding='utf-8')

with open("/home/jovyan/.paddlex/official_models/PP-OCRv5_server_rec/inference.yml") as f:
    cfg = yaml.safe_load(f)
char_dict = cfg["PostProcess"]["character_dict"]

print(f"char_dict[0:5] = {[char_dict[i] for i in range(min(5,len(char_dict)))]}")
print(f"char_dict[10:15] = {[char_dict[i] for i in range(10,15)]}")

rec = ort.InferenceSession(
    "/home/jovyan/.paddlex/official_models/PP-OCRv5_server_rec/inference.onnx",
    ort.SessionOptions(), providers=["CPUExecutionProvider"]
)
rn = rec.get_inputs()[0].name

# Test with synthetic image: "ABC123"
img = np.full((48, 160, 3), 255, dtype=np.uint8)
cv2.putText(img, "ABC123", (5, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

rmean = np.array([0.5, 0.5, 0.5], dtype=np.float32)
rstd = np.array([0.5, 0.5, 0.5], dtype=np.float32)
inp = np.transpose((img.astype(np.float32) / 255.0 - rmean) / rstd, (2, 0, 1))[None].astype(np.float32)
print(f"input: {inp.shape}")

logits = rec.run(None, {rn: inp})[0][0]
print(f"logits: {logits.shape}")

idx = np.argmax(logits, axis=1)
print(f"indices: {list(idx[:40])}")

dec = []
prev = -1
for i in idx:
    i = int(i)
    if i != prev and i != 0 and i < len(char_dict):
        dec.append(char_dict[i])
    prev = i
print(f"decoded chars: {dec}")
print(f"decoded text: {''.join(dec)}")
