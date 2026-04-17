# 领导干部个人有关事项报告表 - OCR识别与比对系统

## 项目概述

本系统用于自动识别领导干部个人有关事项报告表（手写扫描件），并与上级查核反馈信息进行比对，标记不一致项，生成综合比对报告。

### 核心功能

1. **PDF 报告表 OCR 识别** - 识别手写扫描件中的填写内容
2. **字段智能提取** - 从识别结果中提取 28 个章节的关键字段
3. **反馈信息读取** - 解析 Excel 格式的查核反馈信息
4. **自动化比对** - 报告表内容与反馈信息逐项比对
5. **差异报告生成** - 标记不一致项并生成可视化报告

---

## 系统架构

### C/S 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    局域网环境                                │
│  ┌───────────────────┐         ┌─────────────────────────┐  │
│  │   Client (浏览器)  │  HTTP   │   Server (高配机)       │  │
│  │   Win7/Win10/11   │ ←────→  │   Python + PaddleOCRVL  │  │
│  │   零安装           │  JSON   │   Flask/FastAPI        │  │
│  └───────────────────┘         └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| OCR 引擎 | PaddleOCRVL | 文档理解引擎，支持表格识别 |
| 服务框架 | FastAPI | 高性能 Python Web 框架 |
| PDF 处理 | PyMuPDF / pdf2image | PDF 转图片 |
| Excel 处理 | openpyxl | 读取反馈 Excel |
| 前端 | 原生 HTML/CSS/JS | 零构建工具，零依赖 |

---

## 数据结构

### 报告表（22 页，28 个章节）

详见：[报告表字段清单.md](报告表字段清单.md)

| 章节 | 内容 |
|------|------|
| 第一章 | 报告人基本信息 |
| 第二章 | 本人基本情况 |
| 第三章 | 本人婚姻情况 |
| 第四章 | 本人健康状况 |
| 第五章 | 本人持有护照情况 |
| ... | ... |
| 第二十八章 | 其他事项 |

### 反馈信息（Excel，多 Sheet）

| Sheet | 对应章节 | 比对字段 |
|-------|----------|----------|
| 房产 | 境内房产/境外房产 | 姓名、地址、面积 |
| 保险 | 境内/境外投资型保险 | 姓名、保单号、保险公司 |
| 基金 | 境内基金/境外基金 | 姓名、基金名称/代码 |
| 护照1/护照2 | 本人护照 | 姓名、护照号 |
| 通行证 | 港澳台通行证 | 姓名、证件号 |
| 出入境 | 因私出国/港澳台 | 姓名、日期、国家 |
| 法人 | 投资企业 | 姓名、企业名称 |
| ... | ... | ... |

---

## API 接口设计

### 文件接口

```
POST /api/upload/pdf
    上传 PDF 报告表
    Response: { "file_id": "xxx", "page_count": 22 }

POST /api/upload/excel
    上传 Excel 反馈文件
    Response: { "file_id": "xxx", "sheets": [...] }
```

### OCR 接口

```
POST /api/ocr/recognize
    执行 OCR 识别
    Body: { "file_id": "xxx", "pages": [1,2,3] }
    Response: { "task_id": "xxx", "status": "processing" }

GET /api/ocr/status/{task_id}
    查询识别进度
    Response: { "status": "completed", "progress": 100, "result": {...} }
```

### 比对接口

```
POST /api/compare
    执行比对分析
    Body: { "report_file_id": "xxx", "feedback_file_id": "xxx" }
    Response: { "compare_id": "xxx", "summary": {...} }

GET /api/compare/result/{compare_id}
    获取比对结果
    Response: { "diff_items": [...], "statistics": {...} }
```

### 报告接口

```
GET /api/report/{compare_id}
    生成比对报告
    Response: HTML 格式报告页面
```

---

## 开发计划

### 阶段一：Server 端开发

- [ ] 项目结构搭建
- [ ] PDF 处理服务（转图片）
- [ ] OCR 识别服务（PaddleOCRVL）
- [ ] Excel 处理服务
- [ ] 字段提取服务（28 章节）
- [ ] 比对服务（差异分析）
- [ ] API 接口开发（FastAPI）
- [ ] 部署打包（虚拟环境拷贝）

### 阶段二：Client 端开发

- [ ] 页面结构设计
- [ ] 文件上传组件
- [ ] 任务状态显示
- [ ] 结果展示组件
- [ ] 导出功能

### 阶段三：联调测试

- [ ] 功能测试
- [ ] 离线部署验证
- [ ] 局域网访问测试

---

## 部署要求

### 系统要求

**Server 端（高配机）**：
- Windows 10/11（64位）
- **16GB+ 内存**（PaddleOCRVL 约需 4-8GB）
- 预留 15GB+ 磁盘空间

> ⚠️ **注意**：PaddleOCRVL 模型加载后内存占用约 4-8GB，请确保系统有足够内存。

**Client 端（低配机）**：
- Windows 7/10/11
- 任意配置
- 只需浏览器即可访问

### 部署方式

**零下载依赖**：
1. Server 端预装 Python 3.11.x (x64)
2. 拷贝完整虚拟环境
3. 一键启动服务
4. 局域网内浏览器访问

---

## 项目结构

```
报告表比对服务/
├── server.py              # FastAPI 主入口
├── api/                   # API 路由
│   ├── __init__.py
│   ├── upload.py          # 文件上传
│   ├── ocr.py             # OCR 识别
│   ├── compare.py         # 比对分析
│   └── report.py          # 报告生成
├── services/              # 业务服务层
│   ├── pdf_service.py
│   ├── ocr_service.py
│   ├── excel_service.py
│   ├── extract_service.py
│   └── compare_service.py
├── models/                # 数据模型
├── config/                # 配置文件
│   └── fields.py          # 28 章节字段定义
├── templates/             # 前端页面
│   └── index.html
├── static/                # 静态资源
├── .venv_paddleocr/       # Python 虚拟环境
└── start.bat              # 启动脚本
```

---

## 版本信息

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-04-13 | 初始规划 |

---

## 参考文档

- [报告表字段清单.md](报告表字段清单.md)
- [报告表字段结构.json](报告表字段结构.json)
- [paddle环境配置过程.txt](paddle环境配置过程.txt)
