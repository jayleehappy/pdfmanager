import sys, os, re
sys.path.insert(0, r'D:/grsxbd/.venv_paddleocr/Lib/site-packages')
src = open(r'D:/grsxbd/.venv_paddleocr/Lib/site-packages/paddleocr/_pipelines/vl/pipeline.py', encoding='utf-8', errors='replace').read()

# Find all quoted strings that look like model names
matches = re.findall(r'["\']([A-Za-z0-9_\-\.]+)["\']', src)
unique = sorted(set([m for m in matches if len(m) > 5 and not m.startswith('http')]))
for m in unique[:60]:
    print(m)
