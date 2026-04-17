from paddleocr import PaddleOCR
from PIL import Image

print("初始化PaddleOCR...")

# 使用本地模型路径（更新参数名）
ocr = PaddleOCR(
    text_detection_model_dir=r'D:\paddle\.paddlex_models\PP-OCRv5_server_det',
    text_recognition_model_dir=r'D:\paddle\.paddlex_models\PP-OCRv5_server_rec',
    lang='ch'
)

print("PaddleOCR初始化成功！")

# 使用已生成的图片
img_path = 'd:/grsxbd/temp_page5.png'

print(f"\n读取图片: {img_path}")

# 执行OCR
print("开始OCR识别...")
result = ocr.ocr(img_path)

print(f"\n识别结果（共{len(result[0]) if result and result[0] else 0}条）：\n")
if result and result[0]:
    for line in result[0]:
        text = line[1][0]
        confidence = line[1][1]
        print(f"  [{confidence:.2f}] {text}")
