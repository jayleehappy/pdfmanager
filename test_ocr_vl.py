# PaddleOCR-VL 测试脚本
# 使用新版 PaddleOCRVL API

from paddleocr import PaddleOCRVL
from pathlib import Path

print("初始化PaddleOCRVL...")

# 初始化 PaddleOCRVL（使用 CPU）
pipeline = PaddleOCRVL()

print("PaddleOCRVL初始化成功！")

# 测试图片
img_path = 'd:/grsxbd/temp_page5.png'

print(f"\n读取图片: {img_path}")

# 执行 OCR
print("开始OCR识别...")
output = pipeline.predict(img_path)

print(f"\n识别结果：")
for res in output:
    res.print()  # 打印结构化输出

    # 也可以保存为 JSON
    # res.save_to_json(save_path="output")
    # res.save_to_markdown(save_path="output")
