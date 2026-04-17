"""验证 paddlev5_ocr 插件的 Python 引擎集成"""
import sys
import os
import time

plugin_dir = r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins"
sys.path.insert(0, plugin_dir)
sys.path.insert(0, os.path.join(plugin_dir, "paddlev5_ocr"))

# mock CallFunc（用于独立测试，不依赖 Qt 主线程）
class _MockCallFunc:
    def delayStop(self, timerID): pass
    def delay(self, func, time, *args): return ""

_call_func_mock = _MockCallFunc()
sys.modules["call_func"] = type(sys)("call_func")
sys.modules["call_func"].CallFunc = _call_func_mock

from importlib import import_module, util
import importlib.util

plugin_pkg = r"D:\grsxbd\Umi-OCR\UmiOCR-data\plugins\paddlev5_ocr"

# 手动构建包
sys.path.insert(0, plugin_pkg)

# mock CallFunc
class _MockCallFunc:
    def delayStop(self, timerID): pass
    def delay(self, func, time, *args): return ""

_call_func_mock = _MockCallFunc()
sys.modules["call_func"] = type(sys)("call_func")
sys.modules["call_func"].CallFunc = _call_func_mock

# 用 spec 方式加载模块，保留相对导入
spec = importlib.util.spec_from_file_location(
    "paddlev5_ocr_dummy", os.path.join(plugin_pkg, "paddlev5_ocr.py"))
mod = importlib.util.module_from_spec(spec)

# 临时 patch PPOCR_api 导入
class _DummyPPOCRApi:
    pass

sys.modules["paddlev5_ocr"] = type(sys)("paddlev5_ocr")
sys.modules["paddlev5_ocr"].PPOCR_api = _DummyPPOCRApi()

# 写入 PPOCR_pipe 作为哑巴（不会真正用到 C++ 引擎）
DummyPipe = type("DummyPipe", (), {
    "__init__": lambda self, *a, **k: None,
})()
sys.modules["paddlev5_ocr"].PPOCR_pipe = DummyPipe

spec.loader.exec_module(mod)

Api = mod.Api
_is_v5_config = mod._is_v5_config

globalArgd = {
    "ram_max": 4096,
    "ram_time": 60,
}

print("=== 测试 Api._start_python() ===")

api = Api(globalArgd)

# 模拟调用 v5 配置
argd = {
    "config_path": "models/config_chinese_v5.txt",
    "cpu_threads": 4,
}

t0 = time.time()
err = api.start(argd)
t1 = time.time()

if err:
    print(f"启动失败: {err}")
else:
    print(f"启动成功，耗时 {t1-t0:.1f}s")

    # 测试识别
    test_img = r"d:\grsxbd\Umi-OCR\test_imgs\page_009.png"
    if os.path.exists(test_img):
        t2 = time.time()
        res = api.runPath(test_img)
        t3 = time.time()
        if res.get("code") == 100:
            lines = res["data"]
            print(f"识别成功，{len(lines)} 行，耗时 {t3-t2:.1f}s")
            for i, line in enumerate(lines[:5]):
                print(f"  {i+1}. {line['text'][:50]}")
            if len(lines) > 5:
                print(f"  ... (共 {len(lines)} 行)")
        else:
            print(f"识别失败: {res}")
    else:
        print(f"测试图片不存在: {test_img}")

    api.stop()
