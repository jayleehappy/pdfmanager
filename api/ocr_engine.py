"""
OCR 引擎核心模块
包含：process_ocr_task（主任务函数）、_save_and_complete、save_results
"""

import os
import json
import time
import shutil
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import fitz
import numpy as np
from PIL import Image

from api.ocr_utils import (
        to_serializable,
        looks_like_name,
        looks_like_date,
        looks_like_org,
        orb_features,
        match_page_orb,
        match_score,
)
from api.ocr_preocr import run_preocr_batch
from api.ocr_coordinator import OcrCoordinator

logger = logging.getLogger(__name__)


# ── OCR 批量处理（引擎无关）────────────────────────────────
def _batch_ocr_paddleocr(image_paths: list[str]) -> list[list[dict]]:
        """
        使用 OCR 引擎批量识别图片。

        引擎由环境变量 OCR_ENGINE_MODE 控制：
          - "fast"（默认）: PP-OCRv5 ONNX Runtime CPU + 多进程池（~6-11s/页）
          - "docker-gpu": PaddleOCR v3 Docker GPU 模式（高质量，GPU 加速）
        """
        mode = os.environ.get("OCR_ENGINE_MODE", "fast")
        from lib.ocr_engines import get_ocr_engine
        engine = get_ocr_engine(mode=mode)
        return [engine.recognize(p) for p in image_paths]

# ── 结果保存 ─────────────────────────────────────────────
def _get_tasks():
        """延迟导入 tasks 字典，避免循环导入"""
        from api.ocr import tasks
        return tasks

def save_results(task_id: str, results: list) -> str:
        """保存 OCR 结果到文件"""
        def json_default(obj):
                if isinstance(obj, np.integer):
                        return int(obj)
                if isinstance(obj, np.floating):
                        return float(obj)
                if isinstance(obj, np.ndarray):
                        return obj.tolist()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        BASE_DIR = Path(__file__).parent.parent
        result_dir = BASE_DIR / "uploads" / "ocr_results"
        result_dir.mkdir(parents=True, exist_ok=True)

        result_file = result_dir / f"{task_id}.json"
        with open(result_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=json_default)

        return str(result_file)


# ── 任务完成 ─────────────────────────────────────────────
def _save_and_complete(task_id, pages_data, db_service, tasks):
        """保存结果并标记完成"""
        result_file = save_results(task_id, pages_data)
        logger.info(f"[OCR Task {task_id}] 结果已保存到: {result_file}")

        try:
                db_service.save_scan_result(task_id, pages_data)
        except Exception as db_err:
                logger.error(f"[OCR Task {task_id}] DB 保存失败: {db_err}")

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["result"] = to_serializable(pages_data)
        tasks[task_id]["result_file"] = result_file

        try:
                db_service.update_scan_task(
                        task_id, "completed", 100,
                        completed_at=datetime.now().isoformat()
                )
        except Exception as db_err:
                logger.error(f"[OCR Task {task_id}] DB 更新失败: {db_err}")

        logger.info(f"[OCR Task {task_id}] 任务完成！")


# ── 主任务函数 ─────────────────────────────────────────────
def process_ocr_task(
        task_id: str,
        pdf_file: str,
        pages: Optional[list],
        template_file: Optional[str] = None,
        tasks: Optional[dict] = None,
):
        """
        后台执行 OCR 任务（标注区域方式）

        流程：
        1. 加载 manifest.json，获取模板页信息
        2. 预处理：删除空白页；检测并删除说明/目录页
        3. 重命名非空白页为连续序号 page_001~N
        4. 页匹配：PreOCR批量匹配（3区域合并→批量OCR→文本评分），ORB fallback
        5. 读取模板页标注区域，按比例缩放到 scan PDF 尺寸
        6. 裁剪并 OCR 每个标注区域
        7. 映射到报告表字段，保存结果
        """
        # tasks 参数 fallback（避免循环导入）
        if tasks is None:
                tasks = _get_tasks()
        BASE_DIR = Path(__file__).parent.parent
        TEMPLATE_BASE = BASE_DIR / "templates"
        REGIONS_DIR = TEMPLATE_BASE / "regions"

        # ── 加载 manifest ─────────────────────────────────────
        manifest_path = TEMPLATE_BASE / "manifest.json"
        if not manifest_path.exists():
                logger.error(f"[OCR Task {task_id}] manifest.json 不存在")
                raise FileNotFoundError("模板 manifest.json 不存在")
        with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        manifest_name = manifest["name"]

        # ── Step 0: 拆分扫描件 → 检测空白 → 删除空白 ─────────
        doc = fitz.open(pdf_file)

        split_dir = Path(pdf_file).parent / "temp_split"
        if split_dir.exists():
                shutil.rmtree(split_dir)
        split_dir.mkdir(parents=True, exist_ok=True)

        t_split_start = time.time()

        # Step 0a: 拆分 + 空白检测
        raw_files = {}
        for i in range(len(doc)):
                zoom = 150 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = doc[i].get_pixmap(matrix=mat, alpha=False)
                fd, tmp = tempfile.mkstemp(suffix='.png')
                os.close(fd)
                pix.save(tmp)
                img_arr = np.array(Image.open(tmp).convert('L'))
                os.unlink(tmp)
                var = float(img_arr.var())
                is_blank = var < 50
                out_pdf = split_dir / f"_raw_{i+1:03d}.pdf"
                page_doc = fitz.open()
                page_doc.insert_pdf(doc, from_page=i, to_page=i)
                page_doc.save(str(out_pdf))
                page_doc.close()
                raw_files[i] = {"path": str(out_pdf), "is_blank": is_blank, "var": round(var, 1), "page_num": i}

        doc.close()
        blank_count = sum(1 for v in raw_files.values() if v["is_blank"])

        # Step 0b: 删除空白页
        non_blank = [dict(info) for info in raw_files.values() if not info["is_blank"]]
        logger.info(f"[OCR Task {task_id}] 空白检测：原始 {len(raw_files)} 页，"
                                f"空白 {blank_count} 页已标记，非空白 {len(non_blank)} 页")

        # Step 0c: 检测并删除说明/目录页
        import cv2
        tpl_images_early = {}
        for pg_str, pg_info in manifest["pages"].items():
                pg_num = int(pg_str)
                if pg_num in (2, 3):
                        img_path = TEMPLATE_BASE / "pages" / pg_info["image"]
                        tpl_images_early[pg_num] = np.array(Image.open(img_path).convert('L'))
        tpl_orb_early = {}
        for tpl_pg, tpl_img in tpl_images_early.items():
                tk, td = orb_features(tpl_img)
                tpl_orb_early[tpl_pg] = (tk, td)

        to_remove = set()
        if len(non_blank) >= 2:
                for check_idx in range(2):
                        info = non_blank[check_idx]
                        _doc = fitz.open(info["path"])
                        _pix = _doc[0].get_pixmap(matrix=fitz.Matrix(150/72, 150/72), alpha=False)
                        _doc.close()
                        _fd, _tmp = tempfile.mkstemp(suffix='.png'); os.close(_fd); _pix.save(_tmp)
                        img = np.array(Image.open(_tmp).convert('L'))
                        os.unlink(_tmp)

                        tk, qdes = orb_features(img)
                        num_kp = len(tk)
                        for tpl_pg, (tktd, tdd) in tpl_orb_early.items():
                                from api.ocr_utils import match_score
                                score = match_score(qdes, None, tdd, num_kp)
                                logger.info(f"  [PreCheck] 非空白第{check_idx+1}页 vs 模板{tpl_pg}: orb={score:.3f}")
                                if score >= 15 and (check_idx + 1) == tpl_pg:
                                        to_remove.add(check_idx)

        if to_remove:
                non_blank = [p for i, p in enumerate(non_blank) if i not in to_remove]
                logger.info(f"[OCR Task {task_id}] 前导页匹配模板说明/目录，已删除 {len(to_remove)} 页，当前 {len(non_blank)} 页")
        else:
                logger.info(f"[OCR Task {task_id}] 前导页未匹配模板说明/目录页，保留全部")

        t_split_ms = (time.time() - t_split_start) * 1000
        logger.info(f"[OCR Task {task_id}] 预处理完成：空白 {blank_count} 页，已删说明/目录 {len(to_remove)} 页，剩余 {len(non_blank)} 页，耗时 {t_split_ms:.0f}ms")

        # Step 0d: 重命名非空白页为连续序号
        for idx, info in enumerate(non_blank):
                old_path = Path(info["path"])
                new_path = split_dir / f"page_{idx+1:03d}.pdf"
                if old_path != new_path:
                        shutil.move(str(old_path), str(new_path))
                        info["path"] = str(new_path)
        logger.info(f"[OCR Task {task_id}] 扫描页序号重命名完成")

        # ── Step 1: 加载模板页图 ──────────────────────────────
        logger.info(f"[OCR Task {task_id}] 加载模板页图...")
        tpl_images = {}
        for pg_str, pg_info in manifest["pages"].items():
                pg_num = int(pg_str)
                img_path = TEMPLATE_BASE / "pages" / pg_info["image"]
                tpl_images[pg_num] = np.array(Image.open(img_path).convert('L'))
        logger.info(f"[OCR Task {task_id}] 模板页图加载完成，共 {len(tpl_images)} 页")

        # ── Step 2: 预取模板 ORB 特征 ─────────────────────────
        logger.info(f"[OCR Task {task_id}] 预取 {len(tpl_images)} 个模板页的 ORB 特征...")
        tpl_orb_cache = {}
        for pg_num, tpl_img in tpl_images.items():
                tk, td = orb_features(tpl_img)
                tpl_orb_cache[pg_num] = (tk, td)
        logger.info(f"[OCR Task {task_id}] 模板 ORB 特征预取完成")

        # ── Step 3: 渲染扫描页为灰度图（序号=在non_blank中的位置，始终 0,1,2...）─
        logger.info(f"[OCR Task {task_id}] [DEBUG] 开始渲染 {len(non_blank)} 个扫描页...")
        scan_imgs = {}
        for idx, info in enumerate(non_blank):  # idx = 序号，始终 0,1,2...
                _doc = fitz.open(info["path"])
                _pix = _doc[0].get_pixmap(matrix=fitz.Matrix(150/72, 150/72), alpha=False)
                _doc.close()
                _fd, _tmp = tempfile.mkstemp(suffix='.png'); os.close(_fd); _pix.save(_tmp)
                img = np.array(Image.open(_tmp).convert('L'))
                os.unlink(_tmp)
                scan_imgs[idx] = img
        logger.info(f"[OCR Task {task_id}] [DEBUG] 扫描页渲染完成，共 {len(scan_imgs)} 页")

        # ── PreOCR 批量页匹配（调用预OCR系统）───────────────
        from api.ocr import _get_db_service

        logger.info(f"[OCR Task {task_id}] [DEBUG] 开始 PreOCR 批量页匹配...")

        t_preocr_start = time.time()
        results, preocr_temp_files = run_preocr_batch(
                scan_imgs=scan_imgs,
                tpl_orb_cache=tpl_orb_cache,
                manifest=manifest,
                task_id=task_id,
                TEMPLATE_BASE=TEMPLATE_BASE,
        )

        scan_to_template = {}
        scan_raw_scores = {}
        scan_match_methods = {}

        for seq_idx, best_tpl, best_score, method in results:
                scan_to_template[seq_idx] = best_tpl
                scan_raw_scores[seq_idx] = best_score
                scan_match_methods[seq_idx] = method
                logger.info(f"[OCR Task {task_id}] 页匹配 seq={seq_idx} -> 模板页{best_tpl} (得分={best_score:.2f}, 方法={method})")

        # 兼容：若结果为空，手动填充（不应该发生）
        for seq_idx in scan_imgs:
                if seq_idx not in scan_to_template:
                        orb_tpl, orb_score = match_page_orb(scan_imgs[seq_idx], tpl_orb_cache, seq_idx)
                        scan_to_template[seq_idx] = orb_tpl
                        scan_raw_scores[seq_idx] = orb_score
                        scan_match_methods[seq_idx] = "orb"

        t_preocr_ms = (time.time() - t_preocr_start) * 1000
        total_pages = len(scan_to_template)
        methods = list(scan_match_methods.values())
        preocr_count = methods.count("preocr")
        orb_count = methods.count("orb")
        logger.info(f"[OCR Task {task_id}] PreOCR匹配完成：{total_pages}页(preocr={preocr_count},orb={orb_count})，耗时 {t_preocr_ms:.0f}ms")

        # ── 页面去重 ─────────────────────────────────────────
        # scan_to_template 键 = PreOCR 返回的 seq_idx = 0-based 位置 in non_blank
        # dup_indices 键也 = 位置 in non_blank
        dup_indices: set[int] = set()
        prev_tpl: int | None = None
        prev_pos: int = -1
        prev_score: float = 0.0
        for pos in range(len(non_blank)):
                tpl = scan_to_template[pos]
                raw = scan_raw_scores[pos]
                is_dup_orb = (raw >= 50 and prev_score >= 50)
                is_dup_preocr = (scan_match_methods[pos] == "preocr" and prev_score >= 0.6 and raw >= 0.6)
                if prev_pos >= 0 and prev_tpl == tpl and (is_dup_orb or is_dup_preocr):
                        dup_indices.add(pos)
                        logger.info(f"  [去重] 位置{pos}(原页{non_blank[pos]['page_num']})与前位置{prev_pos}(原页{non_blank[prev_pos]['page_num']})同时匹配模板{tpl}，分数={raw:.2f} vs {prev_score:.2f}，跳过")
                prev_tpl, prev_pos, prev_score = tpl, pos, raw
        if dup_indices:
                logger.info(f"[OCR Task {task_id}] PreOCR+ORB联合去重，标记 {len(dup_indices)} 页重复")

        # ── 待处理位置列表（均为 non_blank 中的位置索引，非原始页码）──────
        # 用户指定页面参数 pages：原始页码 → 转为位置；未指定则取全部非空白位置
        if pages:
                # pages 是原始页码列表，映射到 non_blank 中的位置
                page_to_pos = {info["page_num"]: idx for idx, info in enumerate(non_blank)}
                all_positions = [page_to_pos[p] for p in pages if p in page_to_pos]
        else:
                all_positions = list(range(len(non_blank)))

        # 过滤掉已去重位置
        position_indices = [pos for pos in all_positions if pos not in dup_indices]
        logger.info(f"[OCR Task {task_id}] 有效页 {len(non_blank)} 页，空白页 {blank_count} 页已跳过，重复扫描 {len(dup_indices)} 页已去重，实际处理 {len(position_indices)} 页")

        # ── OCR 主体 ──────────────────────────────────────────
        all_crop_files = []
        pages_data = []
        try:
                tasks[task_id]["status"] = "processing"
                t_task_start = time.time()

                # ── Step 4-5: 遍历所有页，提取标注区域 ─────────
                for idx, scan_pos in enumerate(position_indices):
                        t_page_start = time.time()
                        prog = int((idx / len(position_indices)) * 30)
                        tasks[task_id]["progress"] = prog
                        try:
                                _get_db_service().update_scan_task(task_id, "processing", prog)
                        except Exception:
                                pass

                        template_page_num = scan_to_template[scan_pos]
                        if template_page_num > manifest.get("effective_pages", 21):
                                logger.warning(f"[OCR Task {task_id}] 扫描页 {non_blank[scan_pos]['page_num']} 超出模板页数")
                                pages_data.append({"page": non_blank[scan_pos]["page_num"] + 1, "matched_template_page": template_page_num, "regions_count": 0, "regions": [], "report_fields": {}, "timing_ms": {}})
                                continue

                        regions_file = REGIONS_DIR / f"{manifest_name}_{template_page_num:03d}_regions.json"
                        if not regions_file.exists():
                                logger.info(f"[OCR Task {task_id}] 扫描页 {non_blank[scan_pos]['page_num']} -> 模板页 {template_page_num} 无标注区域，跳过")
                                pages_data.append({"page": non_blank[scan_pos]["page_num"] + 1, "matched_template_page": template_page_num, "regions_count": 0, "regions": [], "report_fields": {}, "timing_ms": {}})
                                continue

                        with open(regions_file, encoding="utf-8") as f:
                                regions_data = json.load(f)
                                template_regions = regions_data.get("regions", [])
                        if not template_regions:
                                pages_data.append({"page": non_blank[scan_pos]["page_num"] + 1, "matched_template_page": template_page_num, "regions_count": 0, "regions": [], "report_fields": {}, "timing_ms": {}})
                                continue

                        tpl_png = TEMPLATE_BASE / "pages" / manifest["pages"][str(template_page_num)]["image"]
                        with Image.open(tpl_png) as tpl_img:
                                tpl_w, tpl_h = tpl_img.size

                        scan_gray = scan_imgs[scan_pos]
                        scan_w, scan_h = scan_gray.shape[1], scan_gray.shape[0]
                        scale_x = scan_w / tpl_w
                        scale_y = scan_h / tpl_h
                        logger.info(f"[OCR Task {task_id}] 扫描页 {non_blank[scan_pos]['page_num']} ({scan_w}x{scan_h}) <- 模板页 {template_page_num} ({tpl_w}x{tpl_h}), scale=({scale_x:.3f},{scale_y:.3f})")

                        page_regions = []
                        for reg in template_regions:
                                x1 = int(reg["x1"] * scale_x)
                                y1 = int(reg["y1"] * scale_y)
                                x2 = int(reg["x2"] * scale_x)
                                y2 = int(reg["y2"] * scale_y)
                                x1, x2 = max(0, x1), min(scan_w, x2)
                                y1, y2 = max(0, y1), min(scan_h, y2)
                                if x2 <= x1 or y2 <= y1:
                                        continue
                                cropped = scan_gray[y1:y2, x1:x2]
                                tmp_fd, tmp_path = tempfile.mkstemp(suffix='.png', prefix=f'ocr_p{non_blank[scan_pos]["page_num"]}_r{reg["index"]}_')
                                os.close(tmp_fd)
                                Image.fromarray(cropped).save(tmp_path)
                                all_crop_files.append({"page_idx": idx, "page": non_blank[scan_pos]["page_num"] + 1, "template_page": template_page_num, "region_idx": reg["index"], "label": reg.get("label", ""), "bbox": (x1, y1, x2, y2), "temp_path": tmp_path})
                                page_regions.append({"region_index": reg["index"], "label": reg.get("label", ""), "bbox": (x1, y1, x2, y2)})
                        logger.info(f"[OCR Task {task_id}] 扫描页 {non_blank[scan_pos]['page_num']} -> 模板页 {template_page_num}，{len(page_regions)} 个区域")
                        t_page_elapsed = (time.time() - t_page_start) * 1000
                        pages_data.append({"page": non_blank[scan_pos]["page_num"] + 1, "matched_template_page": template_page_num, "regions_count": len(page_regions), "regions": page_regions, "report_fields": {}, "timing_ms": {"region_extract_ms": round(t_page_elapsed, 1)}})

                logger.info(f"[OCR Task {task_id}] 区域提取完成，共 {len(all_crop_files)} 个区域待 OCR")

                if not all_crop_files:
                        t_total_ms = (time.time() - t_task_start) * 1000
                        for p in pages_data:
                                p["timing_ms"]["total_ms"] = round(t_total_ms, 1)
                        tasks[task_id]["progress"] = 30
                        _save_and_complete(task_id, pages_data, _get_db_service(), tasks)
                        # 清理 PreOCR 临时文件
                        for pf in preocr_temp_files:
                                try:
                                        if os.path.exists(pf):
                                                os.unlink(pf)
                                except Exception:
                                        pass
                        return

                # ── Step 6: 批量 OCR（PaddleOCR-json）───────────
                t_ocr_start = time.time()
                logger.info(f"[OCR Task {task_id}] Step 6: 批量 OCR 中...")
                all_paths = [r["temp_path"] for r in all_crop_files]
                ocr_results_raw = _batch_ocr_paddleocr(all_paths)

                # 适配返回格式：PaddleOCR 返回 [{'text': '...', 'score': 0.99, 'box': [...]}, ...]
                # 转换为 {'texts': [{'content': '...'}, ...]} 格式（兼容现有逻辑）
                ocr_results = []
                for raw_items in ocr_results_raw:
                        texts = [{"content": item.get("text", ""), "score": item.get("score", 0)} for item in (raw_items or [])]
                        ocr_results.append({"texts": texts})

                t_ocr_elapsed = (time.time() - t_ocr_start) * 1000
                logger.info(f"[OCR Task {task_id}] OCR 完成，共 {len(ocr_results)} 个结果，耗时 {t_ocr_elapsed:.0f}ms")

                # ── Step 7: 组装结果，映射字段 ─────────────────
                for ri, ocr_res in enumerate(ocr_results):
                        crop_meta = all_crop_files[ri]
                        pmi = crop_meta["page_idx"]
                        texts = ocr_res.get('texts', [])
                        text_contents = [t['content'].strip() for t in texts if t.get('content', '').strip()]
                        fields = {}
                        for content in text_contents:
                                c = content.strip()
                                if not c:
                                        continue
                                if looks_like_name(c):
                                        fields.setdefault("姓名", []).append(c)
                                elif looks_like_date(c):
                                        fields.setdefault("日期", []).append(c)
                                elif looks_like_org(c):
                                        fields.setdefault("工作单位", []).append(c)
                        if pmi < len(pages_data):
                                pages_data[pmi]["regions"][crop_meta["region_idx"] - 1] = {"region_index": crop_meta["region_idx"], "label": crop_meta["label"], "bbox": crop_meta["bbox"], "ocr_result": to_serializable(ocr_res), "report_fields": fields}
                                pages_data[pmi]["report_fields"].update(fields)
                        prog = 30 + int(((ri + 1) / len(all_crop_files)) * 70)
                        tasks[task_id]["progress"] = min(prog, 99)
                        try:
                                _get_db_service().update_scan_task(task_id, "processing", min(prog, 99))
                        except Exception:
                                pass

                # ── 计时汇总 ───────────────────────────────────
                t_total_ms = (time.time() - t_task_start) * 1000
                pages_with_regions = sum(1 for p in pages_data if p["regions_count"] > 0)
                ocr_per_page_ms = t_ocr_elapsed / pages_with_regions if pages_with_regions > 0 else 0
                for p in pages_data:
                        if p["regions_count"] > 0:
                                p["timing_ms"]["ocr_batch_ms"] = round(ocr_per_page_ms, 1)
                                p["timing_ms"]["total_ms"] = round(t_total_ms, 1)
                logger.info(f"[OCR Task {task_id}] 总耗时: {t_total_ms:.0f}ms (区域提取: {t_ocr_elapsed:.0f}ms)")

                # ── Step 8: 保存并完成 ─────────────────────────
                _save_and_complete(task_id, pages_data, _get_db_service(), tasks)

                # ── Step 9: 清理临时文件 ───────────────────────
                logger.info(f"[OCR Task {task_id}] Step 9: 清理临时文件...")
                # 清理主 OCR 裁剪图临时文件
                for region_meta in all_crop_files:
                        try:
                                if os.path.exists(region_meta["temp_path"]):
                                        os.unlink(region_meta["temp_path"])
                        except Exception as e:
                                logger.warning(f"[OCR Task {task_id}] 清理裁剪图临时文件失败: {e}")
                # 清理 PreOCR 合并图临时文件
                if preocr_temp_files:
                        for p in preocr_temp_files:
                                try:
                                        if os.path.exists(p):
                                                os.unlink(p)
                                except Exception as e:
                                        logger.warning(f"[OCR Task {task_id}] 清理PreOCR临时文件失败: {e}")
                logger.info(f"[OCR Task {task_id}] 全部完成！")

        except Exception as e:
                logger.error(f"[OCR Task {task_id}] 任务失败: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = str(e)
                for region_meta in all_crop_files:
                        try:
                                if os.path.exists(region_meta["temp_path"]):
                                        os.unlink(region_meta["temp_path"])
                        except Exception:
                                pass
                try:
                        _get_db_service().update_scan_task(task_id, "failed", tasks[task_id].get("progress", 0), error=str(e))
                except Exception:
                        pass
