import urllib.request, os

os.makedirs('/home/jovyan/.paddlex/official_models', exist_ok=True)

models = [
    'https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_server_det_infer.tar',
    'https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_server_rec_infer.tar',
]

for url in models:
    fname = url.split('/')[-1]
    fpath = f'/home/jovyan/.paddlex/official_models/{fname}'
    if os.path.exists(fpath):
        size = os.path.getsize(fpath) / 1024 / 1024
        print(f'已存在: {fname} ({size:.1f} MB)')
        continue
    print(f'下载 {fname} ...')
    try:
        urllib.request.urlretrieve(url, fpath)
        size = os.path.getsize(fpath) / 1024 / 1024
        print(f'完成: {fname} ({size:.1f} MB)')
    except Exception as e:
        print(f'失败: {fname} - {e}')
        os.remove(fpath) if os.path.exists(fpath) else None
