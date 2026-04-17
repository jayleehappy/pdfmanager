import os
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'

import paddle
import paddleocr
paddle.set_flags({'FLAGS_enable_pir_api': False, 'FLAGS_enable_pir_in_executor': False})

from paddleocr import PaddleOCR
import numpy as np

try:
    from pdf2image import convert_from_path  # type: ignore
except ImportError:
    print("Error: pdf2image module not found. Please install it using: pip install pdf2image")
    convert_from_path = None
ocr = PaddleOCR(use_angle_cls=True, lang='ch')
if convert_from_path is not None:
    images = convert_from_path('D:/grsxbd/uploads/pdf/temp_split/page_002.pdf', dpi=200)
    result = ocr.predict(np.array(images[0]))

    # 提取文字
    text = '\n'.join([line[1][0] for line in result[0]])
    print(text)
else:
    print("Cannot proceed: pdf2image is not available")