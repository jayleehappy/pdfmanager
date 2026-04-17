"""
报告生成 API 路由
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pathlib import Path
import json

router = APIRouter()


@router.get("/{compare_id}")
async def generate_report(compare_id: str):
    """
    生成 HTML 比对报告

    Args:
        compare_id: 比对结果 ID

    Returns:
        HTML 报告页面
    """
    BASE_DIR = Path(__file__).parent.parent
    result_dir = BASE_DIR / "uploads" / "compare_results"
    result_file = result_dir / f"compare_{compare_id}.json"

    if not result_file.exists():
        raise HTTPException(status_code=404, detail="比对结果不存在")

    with open(result_file, "r", encoding="utf-8") as f:
        compare_result = json.load(f)

    # 生成 HTML 报告
    html = generate_html_report(compare_result)

    return HTMLResponse(content=html)


def generate_html_report(compare_result: dict) -> str:
    """
    生成 HTML 报告

    Args:
        compare_result: 比对结果

    Returns:
        HTML 字符串
    """
    summary = compare_result.get("summary", {})
    stats = summary.get("statistics", {})
    diff_items = compare_result.get("diff_items", [])
    compare_time = summary.get("compare_time", "")

    # 分类差异项
    inconsistent = [d for d in diff_items if d.get("result") == "不一致"]
    missing = [d for d in diff_items if d.get("result") == "缺失"]

    compare_id = compare_result.get("compare_id", "N/A")

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>比对报告 - {compare_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Microsoft YaHei", sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            font-size: 24px;
            margin-bottom: 10px;
        }}
        .header .meta {{
            opacity: 0.9;
            font-size: 14px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-card .number {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-card .label {{
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }}
        .stat-card.danger .number {{
            color: #e74c3c;
        }}
        .stat-card.warning .number {{
            color: #f39c12;
        }}
        .section {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            font-size: 18px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-inconsistent {{
            background: #ffeaea;
            color: #e74c3c;
        }}
        .badge-missing {{
            background: #fff3cd;
            color: #856404;
        }}
        .badge-consistent {{
            background: #d4edda;
            color: #155724;
        }}
        .empty-state {{
            text-align: center;
            padding: 40px;
            color: #666;
        }}
        .empty-state .icon {{
            font-size: 48px;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 个人有关事项报告表 比对报告</h1>
            <div class="meta">
                比对时间：{compare_time} &nbsp;|&nbsp;
                比对ID：{compare_result.get("compare_id", "N/A")}
            </div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="number">{stats.get("total", 0)}</div>
                <div class="label">比对总数</div>
            </div>
            <div class="stat-card">
                <div class="number">{stats.get("consistent", 0)}</div>
                <div class="label">一致</div>
            </div>
            <div class="stat-card danger">
                <div class="number">{stats.get("inconsistent", 0)}</div>
                <div class="label">不一致</div>
            </div>
            <div class="stat-card warning">
                <div class="number">{stats.get("missing", 0)}</div>
                <div class="label">缺失</div>
            </div>
        </div>

        <div class="section">
            <h2>⚠️ 不一致项目 ({len(inconsistent)})</h2>
"""

    if inconsistent:
        html += """
            <table>
                <thead>
                    <tr>
                        <th>章节</th>
                        <th>序号</th>
                        <th>字段</th>
                        <th>报告表填写</th>
                        <th>反馈信息</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
"""
        for item in inconsistent:
            html += f"""
                    <tr>
                        <td>{item.get("chapter", "")}</td>
                        <td>{item.get("index", "")}</td>
                        <td>{item.get("field", "")}</td>
                        <td>{item.get("report_value", "")}</td>
                        <td>{item.get("feedback_value", "")}</td>
                        <td><span class="badge badge-inconsistent">不一致</span></td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""
    else:
        html += """
            <div class="empty-state">
                <div class="icon">✅</div>
                <p>所有项目均一致</p>
            </div>
"""

    html += f"""
        </div>

        <div class="section">
            <h2>❓ 缺失项目 ({len(missing)})</h2>
"""

    if missing:
        html += """
            <table>
                <thead>
                    <tr>
                        <th>章节</th>
                        <th>序号</th>
                        <th>字段</th>
                        <th>报告表填写</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
"""
        for item in missing:
            html += f"""
                    <tr>
                        <td>{item.get("chapter", "")}</td>
                        <td>{item.get("index", "")}</td>
                        <td>{item.get("field", "")}</td>
                        <td>{item.get("report_value", "")}</td>
                        <td><span class="badge badge-missing">缺失</span></td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""
    else:
        html += """
            <div class="empty-state">
                <div class="icon">✅</div>
                <p>无缺失项目</p>
            </div>
"""

    html += """
        </div>
    </div>
</body>
</html>
"""

    return html
