@echo off
set FLAGS_enable_pir_api=0
set FLAGS_enable_pir_in_executor=0
python "%~dp0test_ppocr_inner.py" %*
