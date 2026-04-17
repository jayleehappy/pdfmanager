"""
OCR 模板对比性能与效果测试脚本
测试不同参数组合下的速度、差异区域数量和质量
"""

import time
import sys
import os
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from services.template_service import TemplateCompareService
from services.ocr_service import OCRService

# 测试文件路径
BASE_DIR = Path(__file__).parent
TEMPLATE_PDF = BASE_DIR / "uploads/pdf/test_3pages.pdf"
SCAN_PDF_1 = BASE_DIR / "uploads/pdf/7222791f-5248-4e69-9638-e8cd54f1f718.pdf"  # 小文件（模板）
SCAN_PDF_2 = BASE_DIR / "uploads/pdf/7854d5fc-b50f-43ae-bb32-5c8c46b52b6c.pdf"  # 大文件（22页）

ocr_service = OCRService()


def test_template_compare(scan_pdf: Path, template_pdf: Path, params: dict, label: str):
    """测试模板对比，返回耗时和结果"""
    print(f"\n{'='*60}")
    print(f"测试场景: {label}")
    print(f"扫描件: {scan_pdf.name}")
    print(f"模板:   {template_pdf.name}")
    print(f"参数:   {params}")
    print('-' * 60)

    template_service = TemplateCompareService(dpi=params.get('dpi', 150))

    # 阶段1: PDF转图像
    t0 = time.time()
    t_img = template_service.pdf_to_image(template_pdf, page=0)
    s_img = template_service.pdf_to_image(scan_pdf, page=0)
    t0_to_image = time.time() - t0
    print(f"[1] PDF→图像: {t0_to_image:.2f}s")
    print(f"    模板尺寸: {t_img.shape}, 扫描件尺寸: {s_img.shape}")

    # 阶段2: 尺寸归一化
    t1 = time.time()
    t_img_norm, s_img_norm = template_service._normalize_image_size(t_img, s_img)
    t1_norm = time.time() - t1
    print(f"[2] 尺寸归一化: {t1_norm:.3f}s → 归一化后: {s_img_norm.shape}")

    # 阶段3: 差异计算
    t2 = time.time()
    mask = template_service.compute_diff_mask(t_img_norm, s_img_norm, threshold=params['threshold'])
    t2_diff = time.time() - t2
    diff_pixels = int((mask > 0).sum())
    diff_ratio = diff_pixels / mask.size * 100
    print(f"[3] 差异计算: {t2_diff:.3f}s")
    print(f"    差异像素: {diff_pixels:,} ({diff_ratio:.2f}%)")

    # 阶段4: 差异区域检测
    t3 = time.time()
    regions = template_service.find_diff_regions(
        mask,
        min_area=params['min_area'],
        max_regions=params['max_regions']
    )
    t3_regions = time.time() - t3
    print(f"[4] 区域检测: {t3_regions:.3f}s → 发现 {len(regions)} 个区域")

    total_prep = t0_to_image + t1_norm + t2_diff + t3_regions
    print(f"[*] 模板对比准备阶段总计: {total_prep:.2f}s")

    if len(regions) == 0:
        print("    ⚠️ 无差异区域，跳过 OCR 阶段")
        return {
            'label': label,
            'diff_regions': 0,
            'diff_ratio': diff_ratio,
            'prep_time': total_prep,
            'ocr_time': 0,
            'total_time': total_prep,
            'regions': []
        }

    # 阶段5: 裁剪差异区域（不计时，只验证）
    print(f"\n[5] 裁剪并识别前 {min(5, len(regions))} 个区域...")
    sample_results = []
    for i, region in enumerate(regions[:5]):
        cropped = template_service.crop_region(s_img_norm, region)

        t4 = time.time()
        ocr_result = ocr_service.recognize_image(cropped)
        t4_ocr = time.time() - t4

        texts = ocr_result.get('texts', [])
        tables = ocr_result.get('tables', [])
        content_preview = ''
        if texts:
            content_preview = texts[0].get('content', '')[:50].replace('\n', ' ')
        elif tables:
            content_preview = '[表格] ' + tables[0].get('content', '')[:50].replace('\n', ' ')

        print(f"    区域{i+1}: bbox={region}, OCR耗时={t4_ocr:.1f}s, 内容='{content_preview}'")
        sample_results.append({
            'region': region,
            'ocr_time': t4_ocr,
            'texts_count': len(texts),
            'tables_count': len(tables),
            'preview': content_preview
        })

    # 估算全部区域 OCR 时间
    avg_ocr_time = sum(r['ocr_time'] for r in sample_results) / len(sample_results)
    estimated_total_ocr = avg_ocr_time * len(regions)
    print(f"\n[*] 估算总 OCR 时间: {estimated_total_ocr:.1f}s (平均 {avg_ocr_time:.1f}s × {len(regions)} 个区域)")

    return {
        'label': label,
        'diff_regions': len(regions),
        'diff_ratio': diff_ratio,
        'prep_time': total_prep,
        'avg_ocr_time': avg_ocr_time,
        'estimated_total_ocr': estimated_total_ocr,
        'estimated_total_time': total_prep + estimated_total_ocr,
        'regions': sample_results
    }


def test_normal_ocr(pdf_path: Path, page_count: int = 1):
    """测试普通全页 OCR 模式"""
    print(f"\n{'='*60}")
    print(f"测试场景: 普通全页 OCR 模式")
    print(f"文件: {pdf_path.name}")
    print('-' * 60)

    t0 = time.time()
    result = ocr_service.recognize_pdf(pdf_path)
    elapsed = time.time() - t0

    if result.get('success'):
        pages = result.get('pages', [])
        total_texts = sum(len(p.get('result', {}).get('texts', [])) for p in pages)
        total_tables = sum(len(p.get('result', {}).get('tables', [])) for p in pages)
        print(f"[✓] 完成: {elapsed:.1f}s, {len(pages)} 页, {total_texts} 文本块, {total_tables} 表格")
        return {
            'mode': 'normal',
            'pages': len(pages),
            'time': elapsed,
            'texts': total_texts,
            'tables': total_tables
        }
    else:
        print(f"[✗] 失败: {result.get('error')}")
        return {
            'mode': 'normal',
            'error': result.get('error')
        }


def main():
    print("=" * 60)
    print("OCR 模板对比性能与效果测试")
    print("=" * 60)

    results = []

    # === 测试1: 不同参数组合 ===
    print("\n\n>>> 测试 A: 不同 threshold 参数（小文件 test_3pages）")
    for threshold in [20, 30, 50]:
        for min_area in [100, 200, 500]:
            params = {'threshold': threshold, 'min_area': min_area, 'dpi': 150, 'max_regions': 20}
            label = f"threshold={threshold}, min_area={min_area}"
            r = test_template_compare(SCAN_PDF_1, TEMPLATE_PDF, params, label)
            results.append(r)

    print("\n\n>>> 测试 B: 不同 DPI 设置")
    for dpi in [100, 150, 200]:
        params = {'threshold': 30, 'min_area': 200, 'dpi': dpi, 'max_regions': 20}
        label = f"dpi={dpi}"
        r = test_template_compare(SCAN_PDF_1, TEMPLATE_PDF, params, label)
        results.append(r)

    print("\n\n>>> 测试 C: 不同文件对比（test_3pages vs 7222791f）")
    params = {'threshold': 30, 'min_area': 200, 'dpi': 150, 'max_regions': 20}
    r = test_template_compare(SCAN_PDF_1, TEMPLATE_PDF, params, "小文件 vs 模板")
    results.append(r)

    # === 速度对比表 ===
    print("\n\n" + "=" * 60)
    print("速度对比汇总")
    print("=" * 60)
    print(f"{'场景':<35} {'差异区域':>8} {'差异率':>8} {'准备(s)':>8} {'OCR/区(s)':>10} {'估算总(s)':>10}")
    print("-" * 80)
    for r in results:
        avg = r.get('avg_ocr_time', 0)
        est = r.get('estimated_total_time', 0)
        print(f"{r['label']:<35} {r['diff_regions']:>8} {r['diff_ratio']:>7.2f}% {r['prep_time']:>8.2f} {avg:>10.1f} {est:>10.1f}")

    # === 普通模式基准测试 ===
    print("\n\n>>> 测试 D: 普通全页 OCR 基准（test_3pages 第一页）")
    normal_result = test_normal_ocr(TEMPLATE_PDF)
    results.append(normal_result)

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

    # 保存测试结果
    output_file = BASE_DIR / "uploads/ocr_results/test_results.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"测试结果已保存: {output_file}")


if __name__ == "__main__":
    main()
