"""
OCR 识别服务
使用 PaddleOCRVL 进行文字识别
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

# 禁用模型源检查
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

from paddleocr import PaddleOCRVL


def _ensure_native(obj):
    """将 numpy 类型深度转换为 Python 原生类型"""
    import numpy as np
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return _ensure_native(obj.tolist())
    if isinstance(obj, dict):
        return {k: _ensure_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_ensure_native(v) for v in obj]
    return obj


class OCRService:
    """OCR 识别服务"""

    _instance = None
    _pipeline = None

    def __new__(cls):
        """单例模式，初始化一次 OCR 引擎"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化 OCR 引擎（CPU 模式）"""
        if self._pipeline is None:
            print("[INFO] Initialize PaddleOCRVL engine (CPU mode)...")
            # 使用 CPU 模式，启用内部队列提升处理效率
            self._pipeline = PaddleOCRVL(
                device="cpu",          # 使用 CPU 模式
                use_queues=True,       # 启用内部队列，异步并行处理
                enable_mkldnn=True,   # 启用 MKL-DNN 加速
                cpu_threads=8,        # CPU 推理线程数
                use_layout_detection=True,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_chart_recognition=False,
                use_seal_recognition=False,
                merge_layout_blocks=True,
            )
            print("[OK] PaddleOCRVL initialization complete (CPU mode with MKL-DNN)")

    def recognize_pdf(self, pdf_path: str | Path) -> Dict[str, Any]:
        """
        直接识别 PDF 文件（优化版：拆分 + 批量处理）

        Args:
            pdf_path: PDF 文件路径

        Returns:
            识别结果字典
        """
        import fitz  # PyMuPDF 用于拆分 PDF
        pdf_path = str(pdf_path)
        pdf_dir = Path(pdf_path).parent
        split_dir = pdf_dir / "temp_split"

        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        try:
            print(f"[OCR] 开始识别 PDF: {pdf_path}")

            # Step 1: 拆分为单页 PDF（比转为图片快很多）
            split_dir.mkdir(parents=True, exist_ok=True)
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            single_page_pdfs = []

            for i in range(page_count):
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=i, to_page=i)
                single_pdf_path = split_dir / f"page_{i+1:03d}.pdf"
                new_doc.save(str(single_pdf_path))
                new_doc.close()
                single_page_pdfs.append(str(single_pdf_path))
            doc.close()
            print(f"[OCR] PDF 已拆分为 {page_count} 个单页文件")

            # Step 2: 传入文件列表，批量处理（官方推荐的高效方式）
            print(f"[OCR] 开始批量识别...")
            output = self._pipeline.predict(single_page_pdfs)
            results = list(output)

            # 解析每页结果
            pages_data = []
            for i, res in enumerate(results):
                result_json = res.json if hasattr(res, 'json') else res
                parsed = self._parse_result(result_json)
                pages_data.append({
                    "page": i + 1,
                    "result": parsed
                })
                print(f"[OCR] 第 {i+1}/{len(results)} 页识别完成")

            return _ensure_native({
                "success": True,
                "pages": pages_data,
                "total_pages": len(results)
            })

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "pages": []
            }

    def recognize_image(self, image_array) -> Dict[str, Any]:
        """
        识别图像数组（用于差异区域识别）

        Args:
            image_array: numpy 数组（灰度图像）

        Returns:
            识别结果字典
        """
        try:
            # 将 numpy 数组转为 PIL Image
            from PIL import Image
            import tempfile

            # numpy 数组转 PIL Image
            if image_array.ndim == 2:
                pil_img = Image.fromarray(image_array)
            else:
                pil_img = Image.fromarray(image_array)

            # 保存为临时文件
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                temp_path = f.name

            pil_img.save(temp_path)

            # 使用已有的 recognize 方法识别
            result = self.recognize(temp_path)

            # 删除临时文件
            Path(temp_path).unlink()

            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "texts": [],
                "tables": []
            }

    def recognize(self, image_path: str | Path) -> Dict[str, Any]:
        """
        识别单张图片

        Args:
            image_path: 图片路径

        Returns:
            识别结果字典，包含：
            - layout_det_res: 版面分析结果
            - parsing_res_list: 解析结果列表
            - raw: 原始结果
        """
        image_path = str(image_path)

        if not Path(image_path).exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        try:
            # 执行识别
            output = self._pipeline.predict(image_path)
            results = list(output)

            if not results:
                return {
                    "success": False,
                    "error": "未识别到任何内容",
                    "texts": [],
                    "tables": []
                }

            # 解析结果
            result = results[0]
            result_json = result.json if hasattr(result, 'json') else result

            # 提取文本和表格
            texts = []
            tables = []

            if isinstance(result_json, dict):
                res_data = result_json.get('res', result_json)

                # 提取文本块
                parsing_list = res_data.get('parsing_res_list', [])
                for item in parsing_list:
                    block_label = item.get('block_label', '')
                    block_content = item.get('block_content', '')

                    if block_content:
                        if block_label == 'table':
                            tables.append({
                                'content': block_content,
                                'bbox': item.get('block_bbox', [])
                            })
                        else:
                            texts.append({
                                'label': block_label,
                                'content': block_content,
                                'bbox': item.get('block_bbox', [])
                            })

            return _ensure_native({
                "success": True,
                "texts": texts,
                "tables": tables,
                "raw": result_json
            })

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "texts": [],
                "tables": []
            }

    def recognize_batch(self, image_paths: list) -> list:
        """
        批量识别多张图片（优化版：批量提交以提高 GPU 利用率）

        Args:
            image_paths: 图片路径列表

        Returns:
            识别结果列表
        """
        if not image_paths:
            return []

        total = len(image_paths)
        print(f"  开始批量识别 {total} 张图片...")

        # 一次性传入所有图片路径，由 PaddleOCRVL 内部优化调度
        try:
            output = self._pipeline.predict(image_paths)
            results = []
            for i, res in enumerate(output):
                result_json = res.json if hasattr(res, 'json') else res
                parsed = self._parse_result(result_json)
                print(f"  已完成 {i+1}/{total} 张图片")
                results.append(parsed)
            return results
        except Exception as e:
            print(f"  批量识别失败，回退到逐张识别: {e}")
            # 回退到逐张识别
            results = []
            for i, img_path in enumerate(image_paths):
                print(f"  正在识别第 {i + 1}/{total} 张图片...")
                result = self.recognize(img_path)
                results.append(result)
            return results

    def _parse_result(self, result_json) -> dict:
        """
        解析识别结果

        Args:
            result_json: 原始结果 JSON

        Returns:
            解析后的结果字典
        """
        texts = []
        tables = []

        if isinstance(result_json, dict):
            res_data = result_json.get('res', result_json)
            parsing_list = res_data.get('parsing_res_list', [])
            for item in parsing_list:
                block_label = item.get('block_label', '')
                block_content = item.get('block_content', '')
                if block_content:
                    if block_label == 'table':
                        tables.append({
                            'content': block_content,
                            'bbox': item.get('block_bbox', [])
                        })
                    else:
                        texts.append({
                            'label': block_label,
                            'content': block_content,
                            'bbox': item.get('block_bbox', [])
                        })

        return _ensure_native({
            "success": True,
            "texts": texts,
            "tables": tables,
            "raw": result_json
        })

    def extract_text_only(self, image_path: str | Path) -> str:
        """
        仅提取纯文本（不含表格）

        Args:
            image_path: 图片路径

        Returns:
            纯文本内容
        """
        result = self.recognize(image_path)
        texts = []

        for text_item in result.get('texts', []):
            texts.append(text_item.get('content', ''))

        return '\n'.join(texts)

    def extract_tables(self, image_path: str | Path) -> list:
        """
        仅提取表格（HTML 格式）

        Args:
            image_path: 图片路径

        Returns:
            表格列表，每个表格为 HTML 字符串
        """
        result = self.recognize(image_path)
        return [t.get('content', '') for t in result.get('tables', [])]
