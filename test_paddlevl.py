import sys
sys.path.insert(0, r'D:\grsxbd\Umi-OCR_Paddle_v2.1.5\UmiOCR-data\plugins\paddlevl_ocr')
from paddlevl_engine import get_paddle_vl_engine

model_path = r'D:\grsxbd\Umi-OCR_Paddle_v2.1.5\UmiOCR-data\plugins\paddlevl_ocr\PaddleOCR-VL'
engine = get_paddle_vl_engine(model_path=model_path)
result = engine.recognize(r'D:\grsxbd\uploads\pdf\temp_images\page_009.png')

# 打印所有结果，不限制
print(f'\n===== 识别到 {len(result)} 个文本块 =====\n')
for i, item in enumerate(result):
    print(f'--- 块 {i+1} ---')
    print(f'标签: {item.get("label", "N/A")}')
    print(f'文本: {item["text"]}')
    print(f'坐标: {item["box"]}')
    print(f'置信度: {item.get("score", 1.0)}')
    print()

# 也打印纯文本
print('\n===== 纯文本提取 =====')
print(''.join(item['text'] for item in result))
