# 报告表 OCR 识别与比对系统 - 规范文档

> 编写日期：2026-04-14
> 版本：v1.0.0
> 状态：进行中

---

## 一、目标

将领导干部个人有关事项报告表（扫描件 PDF）通过 OCR 识别，
与组织部门反馈数据（Excel）进行字段级比对，输出差异项清单供人工核查。

---

## 二、技术栈

| 组件 | 技术选型 | 版本/说明 |
|------|---------|---------|
| 后端框架 | FastAPI + Uvicorn | Python 3.10+ |
| OCR 引擎 | PaddleOCR VL 1.5 | CPU 模式，MKL-DNN 加速 |
| PDF 处理 | PyMuPDF (fitz) | PDF 转图像 |
| 图像处理 | PIL + NumPy | 灰度、resize、差分 |
| 科学计算 | SciPy | 连通域检测 |
| 数据库 | SQLite | 结构化数据持久化 |
| 前端 | HTML/JS (原生) | 无框架，最小依赖 |

---

## 三、架构

```
客户端 (浏览器)
    │
    ├── /static/index.html         ← 前端单页应用
    │
    └── FastAPI (server.py)
        │
        ├── api/upload.py          ← 文件上传
        │       uploads/pdf/       ← PDF 存储
        │       uploads/excel/     ← Excel 存储
        │       uploads/ocr_results/  ← OCR 结果 JSON
        │
        ├── api/ocr.py             ← OCR 任务调度
        │       services/ocr_service.py     ← PaddleOCR VL
        │       services/template_service.py ← 模板对比
        │
        ├── api/compare.py          ← 比对分析
        │       services/compare_service.py ← 字段级比对
        │
        ├── api/report.py          ← 报告生成
        │       services/excel_service.py   ← Excel 读取
        │
        └── services/pdf_export_service.py  ← PDF 导出 (TODO)
            services/db_service.py           ← SQLite 操作 (TODO)
```

---

## 四、功能模块

### 4.1 文件上传

- **PDF 上传**：`POST /api/upload/pdf`
  - 保存到 `uploads/pdf/{uuid}.pdf`
  - 返回 `file_id` (uuid)

- **Excel 上传**：`POST /api/upload/excel`
  - 保存到 `uploads/excel/{uuid}.xlsx`
  - Sheet → 章节映射（见 excel_service.py SHEET_MAPPING）

### 4.2 OCR 识别

**普通模式**（无 template_file_id）：
```
POST /api/ocr/recognize
{ "file_id": "uuid" }
```

**模板对比模式**（有 template_file_id）：
```
POST /api/ocr/recognize
{ "file_id": "uuid", "template_file_id": "template_uuid" }
```
流程：
1. 模板 PDF + 扫描件 PDF → 灰度图像
2. 尺寸归一化（以较小尺寸为目标，LANCZOS 缩小）
3. 逐像素差分 → 二值遮罩（threshold=30）
4. 连通域分析 → 差异区域边界框（min_area=200）
5. 仅对差异区域调用 OCR
6. 结果保存到 `uploads/ocr_results/{task_id}.json`

**状态查询**：`GET /api/ocr/status/{task_id}`
**获取结果**：`GET /api/ocr/result/{task_id}`

### 4.3 比对分析

```
POST /api/compare
{ "report_result_file": "ocr_results/uuid.json",
  "feedback_file_id": "excel_uuid" }
```

比对策略（按章节）：
- 房产/基金/保险：按关键字段（地址/名称/保单号）匹配，再逐字段比对
- 护照/通行证：按证件号匹配
- 企业：按企业名称匹配
- 通用：字符串相似度（`is_similar`，阈值 0.7）

比对结果字段：
- `result`: "一致" | "不一致" | "缺失"
- `field`: 比对字段名
- `report_value`: 报告表填写值
- `feedback_value`: 反馈数据值

### 4.4 报告生成

- HTML 报告：`GET /api/report/{compare_id}`
- PDF 导出：`GET /api/export/compare-pdf/{compare_id}` （TODO）
- Excel 导出：`GET /api/export/compare-excel/{compare_id}` （TODO）

### 4.5 结构化数据持久化（TODO）

SQLite 数据库：`data/app.db`

```sql
CREATE TABLE scan_tasks (
    id INTEGER PRIMARY KEY,
    task_id TEXT UNIQUE,
    file_id TEXT,
    mode TEXT,              -- 'normal' | 'template_compare'
    status TEXT,            -- 'pending' | 'processing' | 'completed' | 'failed'
    progress INTEGER,
    created_at DATETIME,
    completed_at DATETIME
);

CREATE TABLE scan_results (
    id INTEGER PRIMARY KEY,
    task_id TEXT,
    data JSON,
    FOREIGN KEY (task_id) REFERENCES scan_tasks(task_id)
);

CREATE TABLE feedback_files (
    id INTEGER PRIMARY KEY,
    file_id TEXT UNIQUE,
    filename TEXT,
    sheet_count INTEGER,
    row_count INTEGER,
    created_at DATETIME
);

CREATE TABLE feedback_data (
    id INTEGER PRIMARY KEY,
    file_id TEXT,
    chapter TEXT,
    data JSON,
    FOREIGN KEY (file_id) REFERENCES feedback_files(file_id)
);

CREATE TABLE compare_results (
    id INTEGER PRIMARY KEY,
    compare_id TEXT UNIQUE,
    task_id TEXT,
    feedback_file_id TEXT,
    stats JSON,
    diff_items JSON,
    created_at DATETIME
);
```

---

## 五、API 契约

### 5.1 文件上传

**POST /api/upload/pdf**
```json
// Request: multipart/form-data, field="file"
// Response 200:
{ "file_id": "uuid", "filename": "xxx.pdf", "size": 1234 }
```

**POST /api/upload/excel**
```json
// Request: multipart/form-data, field="file"
// Response 200:
{ "file_id": "uuid", "filename": "xxx.xlsx", "sheets": ["房产", "保险"] }
```

### 5.2 OCR

**POST /api/ocr/recognize**
```json
// Request
{ "file_id": "uuid", "template_file_id": "uuid|null", "pages": [1,2]|null }

// Response 200
{ "task_id": "uuid", "status": "pending", "message": "OCR 识别任务已创建" }

// Response 404
{ "detail": "PDF 文件不存在" }
```

**GET /api/ocr/status/{task_id}**
```json
// Response 200
{ "task_id": "uuid", "status": "processing", "progress": 45 }

// Response 200 (completed)
{ "task_id": "uuid", "status": "completed", "progress": 100, "result_file": "path/to/file.json" }

// Response 200 (failed)
{ "task_id": "uuid", "status": "failed", "progress": 45, "error": "错误信息" }
```

**GET /api/ocr/result/{task_id}**
```json
// Response 200
{
  "task_id": "uuid",
  "result": [{ "page": 1, "regions": [...], "diff_ratio": 4.5 }],
  "result_file": "path/to/file.json"
}
```

### 5.3 比对

**POST /api/compare**
```json
// Request
{ "report_result_file": "uploads/ocr_results/uuid.json",
  "feedback_file_id": "uuid" }

// Response 200
{ "compare_id": "uuid", "result_file": "path/to/file.json",
  "summary": { "total": 10, "consistent": 8, "inconsistent": 1, "missing": 1 } }
```

**GET /api/compare/result/{compare_id}**
```json
// Response 200
{
  "compare_id": "uuid",
  "summary": { "statistics": {...}, "consistency_rate": "80.0%" },
  "diff_items": [{ "chapter": "境内房产", "field": "面积", "result": "不一致", ... }]
}
```

### 5.4 导出（TODO）

**GET /api/export/scan-pdf/{task_id}**
- 返回 OCR 识别结果的表单式 PDF

**GET /api/export/feedback-pdf/{file_id}**
- 返回反馈数据的表单式 PDF

**GET /api/export/compare-pdf/{compare_id}**
- 返回比对报告 PDF

---

## 六、数据库 Schema

见 4.5 节。

---

## 七、测试策略

### 7.1 差异化比对测试

测试场景：
1. **低填写率**：差异区域占页面 5% 以下
2. **中填写率**：差异区域占页面 5%-20%
3. **高填写率**：差异区域占页面 20% 以上
4. **不同 DPI**：模板 150 DPI vs 扫描件 300 DPI
5. **参数敏感性**：threshold=20/30/50，min_area=100/200/500

测量指标：
- 差异区域数量
- OCR 耗时（总时间 vs 普通模式）
- 识别精度（抽样验证）

### 7.2 比对功能测试

准备数据：
- 反馈 Excel：房产、护照、基金各 1 条
- 测试场景：
  1. 填写内容与反馈完全一致 → 应输出"一致"
  2. 填写内容与反馈不一致（面积差异）→ 应输出"不一致"
  3. 报告表有填写但反馈无 → 应输出"缺失"
  4. 报告表无填写但反馈有 → 应输出"报告表缺失"

---

## 八、已知限制

1. 模板对比仅支持第 1 页（page=0 硬编码）
2. 任务存储在内存，重启丢失
3. 缺少真实手写扫描件测试数据
4. `api/compare.py` 的 `extract_report_data()` 仅为简化版，需精细化
5. PDF 导出、SQLite 持久化尚未实现

---

## 九、边界（Always/Ask First/Never）

**Always：**
- PaddlePaddle 绝对不降级
- 敏感数据（报告表内容）不写入日志
- 所有 API 输入有 Pydantic 校验

**Never：**
- 不在生产环境直接操作数据库
- 不在代码中硬编码文件路径（统一用 BASE_DIR）
- 不删除已有功能（只扩展）
