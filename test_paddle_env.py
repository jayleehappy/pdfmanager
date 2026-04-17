import os
import sys

# 在任何 paddle 模块加载前设置环境变量
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'

# 先验证 paddle 加载前的 flag 状态
print('开始导入 paddle...')

import paddle
print(f'Paddle 版本: {paddle.__version__}')

# 检查 flag 是否生效
flags = paddle.get_flags(['FLAGS_enable_pir_api', 'FLAGS_enable_pir_in_executor'])
print(f'PIR API: {flags}')
