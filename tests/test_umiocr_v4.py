# -*- coding: utf-8 -*-
"""
测试 UmiOCR 使用 PP-OCRv4 模型
"""
import sys, os, time
from pathlib import Path

sys.path.insert(0, r"D:/grsxbd/.venv_paddleocr/Lib/site-packages")
sys.path.insert(0, r"D:/grsxbd/Umi-OCR_Paddle_v2.1.5/UmiOCR-data/plugins/win7_x64_PaddleOCR-json")

from PPOCR_api import PPOCR_pipe

PADDLE_PLUGIN_PATH = Path(r"D:/grsxbd/Umi-OCR_Paddle_v2.1.5/UmiOCR-data/plugins/win7_x64_PaddleOCR-json")
PADDLE_EXE_PATH = PADDLE_PLUGIN_PATH / "PaddleOCR-json.exe"
PADDLE_MODELS_PATH = PADDLE_PLUGIN_PATH / "models"

# 测试图片
img_path = r"D:/grsxbd/tests/paddle_official_test/hybrid_crop_000.png"

def test_config(config_name, config_path):
    """测试指定配置"""
    print(f"\n{'='*60}")
    print(f"测试: {config_name}")
    print(f"{'='*60}")

    argument = {
        "config_path": str(config_path),
        "enable_mkldnn": True,
        "limit_side_len": 960,
        "cls": False,
        "use_angle_cls": False,
    }

    try:
        ocr = PPOCR_pipe(
            str(PADDLE_EXE_PATH),
            modelsPath=str(PADDLE_MODELS_PATH),
            argument=argument
        )
        print(f"引擎初始化成功!")

        # 测试识别
        t0 = time.time()
        result = ocr.run(img_path)
        t1 = time.time()

        print(f"识别时间: {(t1-t0)*1000:.1f}ms")
        print(f"结果: {result}")

        ocr.exit()
        return True
    except Exception as e:
        print(f"错误: {e}")
        import traceback; traceback.print_exc()
        return False

# 测试1: PP-OCRv3 (基准)
test_config("PP-OCRv3 (基准)", PADDLE_MODELS_PATH / "config_chinese.txt")

# 测试2: PP-OCRv4
test_config("PP-OCRv4", PADDLE_MODELS_PATH / "config_chinese_v4.txt")

print("\n完成!")
