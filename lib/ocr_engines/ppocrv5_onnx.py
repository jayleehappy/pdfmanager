"""
PP-OCRv5 ONNX Runtime 引擎 + 多进程 Worker 池

使用 paddle2onnx 将 PP-OCRv5 模型转为 ONNX 格式，
通过 ONNX Runtime 进行 CPU 推理，绕过 PaddlePaddle PIR 的 CPU 兼容性问题。

性能参考（测试图片 1237×1752px, 76文本框）：
  - 原始尺寸: ~24秒/页
  - 缩放至 90dpi: ~11秒/页
  - 缩放至 60dpi: ~6秒/页

多进程池（参考 ocr_pool.py）：
  - Worker 进程数: 4（16核/32G 配置）
  - 每个 Worker 独立加载 ONNX 模型，互相隔离
  - Pool 进程内复用：每次 process() 保持 pool 存活

ONNX 模型位置：
  - 检测模型: paddle/models/PP-OCRv5_server_det/inference.onnx
  - 识别模型: paddle/models/PP-OCRv5_server_rec/inference.onnx
  - 字符表  : paddle/models/PP-OCRv5_server_rec/char_dict_correct.json
    （注意：inference.yml 在 Windows 上读取会编码损坏，需用 config.json 导出的 JSON）
"""

import logging
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from lib.ocr_engines import BaseOCREngine, OCREngineInfo

logger = logging.getLogger(__name__)

# ONNX 模型路径（宿主机，Docker 卷挂载目录）
_MODELS_DIR = Path(__file__).parent.parent.parent / "paddle" / "models"
_DET_MODEL = _MODELS_DIR / "PP-OCRv5_server_det" / "inference.onnx"
_REC_MODEL = _MODELS_DIR / "PP-OCRv5_server_rec" / "inference.onnx"
_CHAR_DICT_FILE = _MODELS_DIR / "PP-OCRv5_server_rec" / "char_dict_correct.json"


# ── Worker 进程入口 ─────────────────────────────────────
_worker_engine = None


def _init_onnx_worker(intra_threads: int = 8, inter_threads: int = 8,
                       rec_max_width: int = 640):
    """每个 Worker 进程启动时执行一次：加载自己的 ONNX Session"""
    global _worker_engine
    _worker_engine = _PPOCRv5Session(
        det_model_path=str(_DET_MODEL),
        rec_model_path=str(_REC_MODEL),
        intra_threads=intra_threads,
        inter_threads=inter_threads,
        rec_max_width=rec_max_width,
    )
    import os as _os
    print(f"[ONNX Worker PID={_os.getpid()}] ONNX sessions loaded, ready", flush=True)


def _worker_ocr_batch(image_paths: list[str]) -> list[list[dict]]:
    """单个 Worker 处理一批图像路径"""
    import os as _os
    print(f"[ONNX Worker PID={_os.getpid()}] Processing {len(image_paths)} images", flush=True)
    global _worker_engine
    if _worker_engine is None:
        raise RuntimeError("ONNX Worker not initialized")
    results = []
    for p in image_paths:
        items = _worker_engine.recognize(p)
        results.append(items)
    print(f"[ONNX Worker PID={_os.getpid()}] Done {len(results)} images", flush=True)
    return results


# ── Worker 进程池 ───────────────────────────────────────

class _ONNXWorkerPool:
    """
    多进程 ONNX Worker 池（进程内复用）

    设计原则（参考 ocr_pool.py）：
      - Pool 在多次 process() 调用间保持存活，避免重复加载 ONNX 模型
      - 每次 process() 完成后检查是否有 chunk 超时
      - 超时的 chunk 在原 pool 中重试（pool 不会 terminate）
    """

    _instance: Optional["_ONNXWorkerPool"] = None

    def __init__(self, workers: int = 4, chunk_size: int = 5,
                 intra_threads: int = 8, inter_threads: int = 8,
                 rec_max_width: int = 640):
        import multiprocessing as mp
        self.workers = workers
        self.chunk_size = chunk_size
        self._intra_threads = intra_threads
        self._inter_threads = inter_threads
        self._rec_max_width = rec_max_width
        self._pool: Optional[mp.Pool] = None
        self._ctx = mp.get_context("spawn")

    @classmethod
    def get_instance(cls, **kwargs) -> "_ONNXWorkerPool":
        if cls._instance is None:
            cls._instance = cls(**kwargs)
            cls._instance.start()
        return cls._instance

    def start(self):
        if self._pool is None:
            import sys
            print(f"[_ONNXWorkerPool] Starting {self.workers} worker processes...", flush=True)
            sys.stdout.flush()
            self._pool = self._ctx.Pool(
                processes=self.workers,
                initializer=_init_onnx_worker,
                initargs=(self._intra_threads, self._inter_threads, self._rec_max_width),
            )
            print(f"[_ONNXWorkerPool] {self.workers} workers ready", flush=True)

    def shutdown(self):
        if self._pool is not None:
            print(f"[_ONNXWorkerPool] Shutting down...", flush=True)
            self._pool.terminate()
            self._pool.join()
            self._pool = None
            _ONNXWorkerPool._instance = None
            print(f"[_ONNXWorkerPool] All workers stopped", flush=True)

    def process(self, image_paths: list[str]) -> list[list[dict]]:
        """并行处理图像路径列表，分块提交，超时重试"""
        if not image_paths:
            return []

        self.start()

        chunks = self._chunk_list(image_paths, self.chunk_size)
        print(f"[_ONNXWorkerPool] Dispatching {len(image_paths)} images -> {len(chunks)} chunks")

        from multiprocessing.pool import AsyncResult
        async_results: list[AsyncResult] = []
        for chunk in chunks:
            ar = self._pool.apply_async(_worker_ocr_batch, args=(chunk,))
            async_results.append(ar)

        results: list[Optional[list[list[dict]]]] = [None] * len(chunks)
        failed_chunks: list[int] = []
        chunk_timeout = 1800  # 30分钟

        for i, ar in enumerate(async_results):
            try:
                results[i] = ar.get(timeout=chunk_timeout)
                print(f"[_ONNXWorkerPool] Chunk {i}/{len(chunks)-1} done")
            except Exception as e:
                print(f"[_ONNXWorkerPool] Chunk {i} ERROR: {e} — will retry")
                results[i] = None
                failed_chunks.append(i)

        if failed_chunks:
            retry_results = self._retry_failed_chunks(failed_chunks, chunks)
            for orig_idx, retry_res in zip(failed_chunks, retry_results):
                results[orig_idx] = retry_res

        final: list[list[dict]] = []
        for chunk_result in results:
            if chunk_result:
                final.extend(chunk_result)
        print(f"[_ONNXWorkerPool] Total results: {len(final)}")
        return final

    def _retry_failed_chunks(self, failed_indices: list[int],
                              all_chunks: list[list[str]]) -> list[Optional[list[list[dict]]]]:
        retry_chunks = [all_chunks[i] for i in failed_indices]
        print(f"[_ONNXWorkerPool] Retrying {len(retry_chunks)} chunks...")

        from multiprocessing.pool import AsyncResult
        async_results: list[AsyncResult] = []
        chunk_timeout = 1800
        for chunk in retry_chunks:
            ar = self._pool.apply_async(_worker_ocr_batch, args=(chunk,))
            async_results.append(ar)

        retry_results: list[Optional[list[list[dict]]]] = [None] * len(retry_chunks)
        for i, ar in enumerate(async_results):
            try:
                retry_results[i] = ar.get(timeout=chunk_timeout)
                print(f"[_ONNXWorkerPool] Retry chunk {i} done")
            except Exception as e:
                print(f"[_ONNXWorkerPool] Retry chunk {i} still failed: {e}")
                retry_results[i] = None
        return retry_results

    def _chunk_list(self, lst: list, size: int) -> list[list]:
        return [lst[i:i+size] for i in range(0, len(lst), size)]


# ── 单次 ONNX 推理会话 ────────────────────────────────────

class _PPOCRv5Session:
    """
    PP-OCRv5 ONNX 单次推理会话（每个 Worker 进程一份）
    """

    def __init__(self, det_model_path: str, rec_model_path: str,
                 intra_threads: int = 8,
                 inter_threads: int = 8, rec_max_width: int = 640):
        import onnxruntime as ort
        import json as _json

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = intra_threads
        opts.inter_op_num_threads = inter_threads
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._det_session = ort.InferenceSession(
            det_model_path, opts, providers=["CPUExecutionProvider"]
        )
        self._rec_session = ort.InferenceSession(
            rec_model_path, opts, providers=["CPUExecutionProvider"]
        )
        self._det_input_name = self._det_session.get_inputs()[0].name
        self._rec_input_name = self._rec_session.get_inputs()[0].name

        with open(str(_CHAR_DICT_FILE), encoding="utf-8") as f:
            self._char_dict = _json.load(f)

        self._det_mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self._det_std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        self._rec_max_width = rec_max_width
        # ONNX 输出 offset=2：index 0=blank, 1=unknown, 2..=实际字符
        self._rec_offset = 2
        # DB 检测阈值（来自 inference.yml）
        self._det_thresh = 0.3       # score map 阈值（原错误地用 0.7）
        self._det_box_thresh = 0.6   # box 得分阈值
        self._det_unclip_ratio = 1.5 # 框扩大比例
        self._det_min_area = 100

    def _preprocess_det(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        max_side = max(h, w)
        scale = 960 / max_side
        new_w = max(32, int(w * scale))
        new_h = max(32, int(h * scale))
        new_w = (new_w + 31) // 32 * 32
        new_h = (new_h + 31) // 32 * 32
        resized = cv2.resize(img, (new_w, new_h))
        normalized = (resized.astype(np.float32) / 255.0 - self._det_mean) / self._det_std
        transposed = np.transpose(normalized, (2, 0, 1))
        return np.expand_dims(transposed, axis=0).astype(np.float32)

    def _detect(self, img: np.ndarray, orig_h: int, orig_w: int) -> list[tuple]:
        """DB 检测 + 正确的后处理（threshold + unclip + box_thresh）"""
        x = self._preprocess_det(img)
        scale_x = orig_w / img.shape[1]
        scale_y = orig_h / img.shape[0]
        score_map = self._det_session.run(None, {self._det_input_name: x})[0][0, 0]

        # Step 1: threshold
        binary = (score_map > self._det_thresh).astype(np.uint8)

        # Step 2: unclip（扩大连通域）
        import scipy.ndimage as ndimage
        kernel = ndimage.generate_binary_structure(2, 1)
        dilated = ndimage.binary_dilation(binary > 0, structure=kernel,
                                          iterations=int(self._det_unclip_ratio * 3))
        dilated = dilated.astype(np.uint8) * 255

        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self._det_min_area:
                continue

            # 计算 contour 区域内的平均得分（box_thresh）
            mask = np.zeros(binary.shape, dtype=np.uint8)
            cv2.drawContours(mask, [c], -1, 1, -1)
            region_scores = score_map[mask > 0]
            if region_scores.size == 0:
                continue
            box_score = float(region_scores.mean())
            if box_score < self._det_box_thresh:
                continue

            # 外接矩形
            rect = cv2.minAreaRect(c)
            pts = cv2.boxPoints(rect)
            x_coords = sorted(pts[:, 0])
            y_coords = sorted(pts[:, 1])
            x1 = max(0, int(x_coords[0] * scale_x))
            x2 = min(orig_w, int(x_coords[2] * scale_x))
            y1 = max(0, int(y_coords[0] * scale_y))
            y2 = min(orig_h, int(y_coords[2] * scale_y))
            if x2 - x1 < 3 or y2 - y1 < 3:
                continue
            boxes.append((x1, y1, x2, y2))
        boxes.sort(key=lambda b: (b[1] // 50, b[0]))
        return boxes

    def _recognize(self, crop_img: np.ndarray) -> tuple[str, float]:
        if crop_img.size == 0:
            return "", 0.0
        h, w = crop_img.shape[:2]
        if h <= 0 or w <= 0:
            return "", 0.0
        # BGR→RGB（PaddleOCR 使用 RGB 输入）
        rgb = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
        # 按高48固定、宽按比例 resize
        target_h = 48
        ratio = w / float(h)
        new_w = int(target_h * ratio)
        new_w = max(8, min(new_w, self._rec_max_width))
        resized = cv2.resize(rgb, (new_w, target_h))
        # PaddleOCR 归一化: (x/255 - 0.5) / 0.5 = 2*x/255 - 1
        normalized = resized.astype(np.float32) * (2.0 / 255.0) - 1.0
        transposed = np.transpose(normalized, (2, 0, 1))
        x = np.expand_dims(transposed, axis=0).astype(np.float32)
        logits = self._rec_session.run(None, {self._rec_input_name: x})[0][0]
        indices = np.argmax(logits, axis=1)
        chars = []
        scores = []
        prev_idx = -1
        for t, idx in enumerate(indices):
            idx = int(idx)
            if idx != prev_idx and idx >= self._rec_offset:
                char_idx = idx - self._rec_offset
                if char_idx < len(self._char_dict):
                    chars.append(self._char_dict[char_idx])
                    scores.append(float(logits[t, idx]))
            prev_idx = idx
        text = "".join(chars)
        avg_score = float(np.mean(scores)) if scores else 0.0
        return text, avg_score

    def recognize(self, image_path: str) -> list[dict]:
        img = cv2.imread(image_path)
        if img is None:
            return []
        orig_h, orig_w = img.shape[:2]
        boxes = self._detect(img, orig_h, orig_w)
        results = []
        for (x1, y1, x2, y2) in boxes:
            crop = img[y1:y2, x1:x2]
            text, score = self._recognize(crop)
            results.append({
                "text": text.strip(),
                "score": round(score, 4),
                "box": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
            })
        return results


# ── 公开引擎接口 ─────────────────────────────────────────

class PPOCRv5ONNXEngine(BaseOCREngine):
    """
    PP-OCRv5 ONNX Runtime 引擎（多进程池）

    特性：
      - 纯 CPU 推理，无需 GPU
      - 检测: DB 网络，识别: SVTR + CTC
      - 支持中文、英文、符号等 18383 类字符
      - 多进程池（4 workers），避免重复加载模型
    """

    @classmethod
    def engine_info(cls) -> OCREngineInfo:
        return OCREngineInfo(
            name="PP-OCRv5-ONNX",
            mode="fast",
            description="PP-OCRv5 Server 模型 + ONNX Runtime CPU + 多进程池（默认引擎）",
            device="cpu",
            speed="medium",
            accuracy="high",
            supports_batch=True,
            requires_docker=False,
        )

    def __init__(
        self,
        det_model_path: Optional[str] = None,
        rec_model_path: Optional[str] = None,
        intra_threads: int = 8,
        inter_threads: int = 8,
        det_thresh: float = 0.3,
        det_box_thresh: float = 0.6,
        det_min_area: int = 100,
        rec_max_width: int = 640,
        workers: int = 4,
        chunk_size: int = 5,
    ):
        self._workers = workers
        self._chunk_size = chunk_size
        self._pool = _ONNXWorkerPool.get_instance(
            workers=workers,
            chunk_size=chunk_size,
            intra_threads=intra_threads,
            inter_threads=inter_threads,
            rec_max_width=rec_max_width,
        )

    def recognize(self, image_path: str) -> list[dict]:
        results = self._pool.process([image_path])
        return results[0] if results else []

    def recognize_array(self, image) -> list[dict]:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp_path = f.name
        try:
            cv2.imwrite(tmp_path, image)
            return self.recognize(tmp_path)
        finally:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass

    def recognize_batch(self, image_paths: list[str]) -> list[list[dict]]:
        return self._pool.process(image_paths)

    def extract_text(self, image_path: str) -> str:
        items = self.recognize(image_path)
        return "".join(item["text"] for item in items if item.get("text"))

    def close(self):
        if self._pool is not None:
            self._pool.shutdown()

    def __repr__(self):
        return f"<PPOCRv5ONNXEngine workers={self._workers}>"
