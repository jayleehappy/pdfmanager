"""
目录扫描器 - 递归扫描工作目录，仅关注目录和 PDF 文件
支持 INI 配置文件自定义排序顺序
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field


# ============================================================
# INI 排序配置（模块级缓存）
# ============================================================
_sort_order_list: List[str] = []          # INI 中的顺序列表
_sort_order_map: Dict[str, int] = {}     # 名称 → INI 排序序号
_display_name_map: Dict[str, str] = {}    # 实际名称 → 显示名称
_config_loaded = False


def _load_sort_config() -> None:
    """加载 sort_order.ini 配置文件"""
    global _sort_order_list, _sort_order_map, _display_name_map, _config_loaded
    if _config_loaded:
        return
    _config_loaded = True

    try:
        base = Path(__file__).parent.parent.parent
        cfg_path = base / "sort_order.ini"
        if not cfg_path.exists():
            return

        with open(cfg_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        in_sort = False
        in_disp = False
        for line in lines:
            raw = line.rstrip("\n\r")
            stripped = raw.strip()
            if stripped.startswith("#") or stripped.startswith(";"):
                continue
            lower_stripped = stripped.lower()
            if stripped == "[SortOrder]":
                in_sort, in_disp = True, False
                continue
            if stripped == "[DisplayNames]":
                in_sort, in_disp = False, True
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_sort, in_disp = False, False
                continue

            if in_sort:
                # 支持 "order=xxx" 格式和纯行格式
                if "=" in stripped:
                    name = stripped.split("=", 1)[1].strip()
                else:
                    name = stripped.strip()
                if name and name not in _sort_order_map:
                    idx = len(_sort_order_list)
                    _sort_order_list.append(name)
                    _sort_order_map[name] = idx

            elif in_disp:
                if "=" in stripped:
                    key, val = stripped.split("=", 1)
                    key, val = key.strip(), val.strip()
                    if key and val:
                        _display_name_map[key] = val
    except Exception:
        pass


def get_display_name(name: str) -> str:
    """获取显示名称：优先 INI 映射，否则去掉 .pdf 后缀"""
    _load_sort_config()
    if name in _display_name_map:
        return _display_name_map[name]
    if name.lower().endswith(".pdf"):
        return name[:-4]
    return name


def natural_sort_key(name: str):
    """
    自然排序键 - 支持 INI 自定义顺序 + 数字/中文数字/英文字母智能排序

    排序优先级：
    1. INI 中定义的项目 → 按 INI 顺序（0, 1, 2...）
    2. 不在 INI 中的项目 → 按自然排序键（-1 表示无 INI 顺序）
       - 前缀序号提取：阿拉伯数字、中文数字、英文字母分别转为可比较的值
       - 前缀相同时，按剩余文字逐字符比较
       - 剩余文字开头的数字段解析为整数（保证 "10-" 排在 "2-" 之后）
    """
    _load_sort_config()

    # ---- 1. INI 顺序优先 ----
    if name in _sort_order_map:
        # 取负值：INI 序号越小越靠前；非 INI 项用 -1 兜底，确保 INI 项排在最前
        return (-1 - _sort_order_map[name], [])

    # ---- 2. 自然排序（无 INI 顺序） ----
    def _get_chinese_value(ch: str) -> int | None:
        return {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                '六': 6, '七': 7, '八': 8, '九': 9,
                '十': 10, '〇': 0, '零': 0}.get(ch)

    def _parse_chinese(s: str):
        if not s:
            return None, s
        digits = []
        for ch in s:
            v = _get_chinese_value(ch)
            if v is not None:
                digits.append(v)
            else:
                break
        if not digits:
            return None, s
        total, unit = 0, 0
        for v in digits:
            if v == 10:
                unit = (unit if unit else 1) * 10
                total += unit
                unit = 0
            else:
                unit = unit * 10 + v if unit else v
        total += unit
        return (total if total > 0 else None), s[len(digits):]

    def _parse_digits(s: str):
        m = re.match(r'^(\d+)', s)
        if m:
            return int(m.group(1)), s[m.end():]
        return None, s

    def _parse_alpha(s: str):
        if s and re.match(r'^[a-zA-Z]$', s[0]):
            return ord(s[0].lower()) - ord('a') + 1, s[1:]
        return None, s

    prefix_val, prefix_len, rest = None, 0, name

    v, r = _parse_digits(name)
    if v is not None:
        prefix_val, prefix_len, rest = v, len(str(v)), r
    v, r = _parse_chinese(name)
    if v is not None and len(name) - len(r) > prefix_len:
        prefix_val, prefix_len, rest = v, len(name) - len(r), r
    v, r = _parse_alpha(name)
    if v is not None and len(name) - len(r) > prefix_len:
        prefix_val, prefix_len, rest = v, len(name) - len(r), r

    if prefix_val is None:
        prefix_val = -1

    # rest 转可比较序列：数字段解析为整数，其余字符转为 ord 保证全为 int
    key_parts = []
    while rest:
        m = re.match(r'^(\d+)', rest)
        if m:
            key_parts.append(int(m.group(1)))
            rest = rest[m.end():]
        else:
            key_parts.append(ord(rest[0]))
            rest = rest[1:]

    return (prefix_val, key_parts)


# ============================================================
# 树节点数据结构
# ============================================================
@dataclass
class TreeNode:
    """树节点数据结构"""
    name: str                                              # 实际名称（文件名或目录名）
    path: str                                              # 完整路径
    is_dir: bool                                           # 是否为目录
    display_name: str = ""                                  # 显示名称（INI映射或去掉后缀）
    children: List['TreeNode'] = field(default_factory=list)
    parent: 'TreeNode' = None

    def __post_init__(self):
        if not self.display_name:
            self.display_name = get_display_name(self.name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'path': self.path,
            'is_dir': self.is_dir,
            'children': [c.to_dict() for c in self.children]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent: 'TreeNode' = None) -> 'TreeNode':
        node = cls(
            name=data['name'],
            path=data['path'],
            is_dir=data['is_dir'],
            parent=parent
        )
        for child_data in data.get('children', []):
            node.children.append(cls.from_dict(child_data, parent=node))
        return node


# ============================================================
# 目录扫描器
# ============================================================
class DirectoryScanner:
    """目录扫描器"""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.supported_extensions = {'.pdf'}

    def scan(self) -> List[TreeNode]:
        if not self.root_path.exists():
            return []
        return self._scan_directory(self.root_path)

    def _scan_directory(self, directory: Path) -> List[TreeNode]:
        nodes = []
        try:
            entries = sorted(directory.iterdir(), key=lambda x: natural_sort_key(x.name))
        except PermissionError:
            return nodes

        for entry in entries:
            name = entry.name
            if name.startswith('.') or name.startswith('~'):
                continue

            if entry.is_dir():
                node = TreeNode(name=name, path=str(entry), is_dir=True)
                node.children = self._scan_directory(entry)
                nodes.append(node)
            elif entry.suffix.lower() in self.supported_extensions:
                nodes.append(TreeNode(name=name, path=str(entry), is_dir=False))

        return nodes

    def get_all_pdf_files(self, nodes: List[TreeNode]) -> List[str]:
        pdf_files = []
        for node in nodes:
            if not node.is_dir:
                pdf_files.append(node.path)
            else:
                pdf_files.extend(self.get_all_pdf_files(node.children))
        return pdf_files


def scan_directory(root_path: str) -> List[TreeNode]:
    """便捷函数：扫描目录"""
    scanner = DirectoryScanner(root_path)
    return scanner.scan()
