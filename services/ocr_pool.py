"""
PaddleOCR 多进程 Worker 池

设计：
- Worker 进程数：4（16核/32G 配置，~2GB 模型内存）
- 每个 Worker 独立加载 PaddleOCRVL，互相隔离
- Pool 进程内复用：每次 process() 保持 pool 存活
- apply_async + AsyncResult.get(timeout) 收集结果
- 失败 chunk 在原 pool 中重试（最多一次）
"""

import multiprocessing as mp
from multiprocessing.pool import AsyncResult
import time
import os
from typing import List, Optional


# ── Worker 进程入口 ──────────────────────────────────────

_worker_ocr = None


def _init_worker():
    """每个 Worker 进程启动时执行一次：加载自己的 OCRService"""
    global _worker_ocr
    import sys
    from pathlib import Path

    _venv_sp = Path(r"C:\Users\jay\.venv_paddleocr\Lib\site-packages")
    if str(_venv_sp) not in sys.path:
        sys.path.insert(0, str(_venv_sp))
    sys.path.insert(0, "D:/grsxbd")

    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ["OMP_NUM_THREADS"] = "2"
    # 解决 Windows MKL-DNN OpenMP 线程死锁
    # 原因：Intel OpenMP 与 Windows 线程调度器竞争，导致 C++ 推理代码冻结
    # 解决：强制使用 GNU OpenMP 线程层
    os.environ["MKL_THREADING_LAYER"] = "GNU"

    from services.ocr_service import OCRService
    _worker_ocr = OCRService()
    print(f"[Worker PID={os.getpid()}] OCRService loaded, ready")


def _worker_recognize(image_paths: List[str]) -> List[dict]:
    """单个 Worker 处理一批图像路径"""
    import os
    print(f"[Worker PID={os.getpid()}] Starting recognize_batch for {len(image_paths)} images", flush=True)
    global _worker_ocr
    if _worker_ocr is None:
        raise RuntimeError("Worker not initialized")
    try:
        result = _worker_ocr.recognize_batch(image_paths)
        print(f"[Worker PID={os.getpid()}] Finished recognize_batch: {len(result)} results", flush=True)
        return result
    except Exception as e:
        print(f"[Worker PID={os.getpid()}] ERROR in recognize_batch: {e}", flush=True)
        raise


# ── Worker 进程池 ────────────────────────────────────────

class OCRWorkerPool:
    """
    多进程 OCR Worker 池（进程内复用）

    设计原则：
    - Pool 在多次 process() 调用间保持存活，避免重复加载 ~4GB 模型
    - 每次 process() 完成后检查是否有 chunk 超时
    - 超时的 chunk 在原 pool 中重试（pool 不会 terminate）
    - 如果重试仍然失败，标记为失败，不影响其他 chunk 的结果
    """

    # 类级别的单例（进程内共享）
    _instance: Optional['OCRWorkerPool'] = None

    def __init__(self, workers: int = 4, chunk_size: int = 5):
        self.workers = workers
        self.chunk_size = chunk_size
        self._pool: Optional[mp.Pool] = None
        self._ctx = mp.get_context('spawn')

    # ── 单例 ─────────────────────────────────────────────

    @classmethod
    def get_instance(cls, workers: int = 4, chunk_size: int = 5) -> 'OCRWorkerPool':
        if cls._instance is None:
            cls._instance = cls(workers=workers, chunk_size=chunk_size)
            cls._instance.start()  # 立即启动 workers
        return cls._instance

    # ── 生命周期 ─────────────────────────────────────────

    def start(self):
        """启动进程池（延迟初始化，已存在的 pool 不重复创建）"""
        import sys
        if self._pool is None:
            print(f"[OCRWorkerPool] Starting {self.workers} worker processes...", flush=True)
            sys.stdout.flush()
            self._pool = self._ctx.Pool(
                processes=self.workers,
                initializer=_init_worker,
                initargs=(),
            )
            print(f"[OCRWorkerPool] {self.workers} workers ready", flush=True)

    def shutdown(self):
        """彻底关闭进程池（仅在服务停止时调用）"""
        if self._pool is not None:
            print(f"[OCRWorkerPool] Shutting down...")
            self._pool.terminate()
            self._pool.join()
            self._pool = None
            print(f"[OCRWorkerPool] All workers stopped")

    # ── 核心处理 ─────────────────────────────────────────

    def process(self, image_paths: List[str]) -> List[dict]:
        """
        并行处理图像路径列表

        策略：
        - 分块后立即 apply_async 提交所有任务
        - 用 get(timeout) 等待每个 chunk，失败时重试一次
        - 池保持复用，worker 进程不销毁

        Returns:
            OCR 结果列表（顺序与输入一致）
        """
        if not image_paths:
            return []

        # 确保 pool 已启动（可复用已存在的）
        self.start()

        chunks = self._chunk_list(image_paths, self.chunk_size)
        print(f"[OCRWorkerPool] Dispatching {len(image_paths)} images -> {len(chunks)} chunks")

        # 提交所有 chunks
        async_results: List[AsyncResult] = []
        for chunk in chunks:
            ar = self._pool.apply_async(_worker_recognize, args=(chunk,))
            async_results.append(ar)

        # 收集结果（首次尝试）
        results: List[Optional[List[dict]]] = [None] * len(chunks)
        failed_chunks: List[int] = []
        chunk_timeout = 1800  # 每个 chunk 最多等 1800 秒（30分钟）

        for i, ar in enumerate(async_results):
            try:
                results[i] = ar.get(timeout=chunk_timeout)
                print(f"[OCRWorkerPool] Chunk {i}/{len(chunks)-1} done")
            except mp.TimeoutError:
                print(f"[OCRWorkerPool] Chunk {i} TIMEOUT after {chunk_timeout}s — will retry")
                results[i] = None
                failed_chunks.append(i)
            except Exception as e:
                print(f"[OCRWorkerPool] Chunk {i} ERROR: {e} — will retry")
                results[i] = None
                failed_chunks.append(i)

        # 重试失败的 chunk（在原 pool 中，不会重新加载模型）
        if failed_chunks:
            retry_results = self._retry_failed_chunks(failed_chunks, chunks)
            for orig_idx, retry_res in zip(failed_chunks, retry_results):
                results[orig_idx] = retry_res

        # 展平结果
        final_results: List[dict] = []
        for chunk_result in results:
            if chunk_result:
                final_results.extend(chunk_result)

        print(f"[OCRWorkerPool] Total results: {len(final_results)}")
        return final_results

    def _retry_failed_chunks(
        self,
        failed_indices: List[int],
        all_chunks: List[List[str]],
    ) -> List[Optional[List[dict]]]:
        """重试失败的 chunk（workers 模型已在内存，无需重新加载）"""
        retry_chunks = [all_chunks[i] for i in failed_indices]
        print(f"[OCRWorkerPool] Retrying {len(retry_chunks)} chunks (workers still warm)...")

        async_results: List[AsyncResult] = []
        for chunk in retry_chunks:
            ar = self._pool.apply_async(_worker_recognize, args=(chunk,))
            async_results.append(ar)

        retry_results: List[Optional[List[dict]]] = [None] * len(retry_chunks)
        for i, ar in enumerate(async_results):
            try:
                retry_results[i] = ar.get(timeout=chunk_timeout)
                print(f"[OCRWorkerPool] Retry chunk {i} done")
            except Exception as e:
                print(f"[OCRWorkerPool] Retry chunk {i} still failed: {e}")
                retry_results[i] = None

        return retry_results

    def _chunk_list(self, lst: List, size: int) -> List[List]:
        return [lst[i:i+size] for i in range(0, len(lst), size)]

    # ── 上下文管理器 ─────────────────────────────────────

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        pass  # 不在 exit 时关闭，保持 pool 复用
