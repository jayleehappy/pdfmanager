"""
PDF 单页拆分引擎 - 将多页 PDF 拆分为多个单页 PDF
每页 PDF 文件名为提取到的姓名（简单文本匹配，无需OCR）
"""
import re
from typing import Optional, Callable, List
from pathlib import Path

from pypdf import PdfReader, PdfWriter


class PDFPageSplitter:
    """
    PDF 单页拆分引擎
    将多页 PDF 按页拆分为多个单页 PDF，文件名使用提取到的姓名
    """

    def __init__(self):
        self._reader: Optional[PdfReader] = None

    def split_to_single_pages(self,
                              input_path: str,
                              output_dir: str,
                              progress_callback: Optional[Callable[[int, int, str], None]] = None
                              ) -> bool:
        """
        将 PDF 按页拆分为单页 PDF

        Args:
            input_path: 输入 PDF 文件路径
            output_dir: 输出目录
            progress_callback: 进度回调函数 (current, total, message)

        Returns:
            是否成功
        """
        try:
            self._reader = PdfReader(input_path)
            num_pages = len(self._reader.pages)

            if num_pages == 0:
                if progress_callback:
                    progress_callback(0, 0, "PDF 无页面")
                return False

            # 创建输出目录
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # 获取输入文件名（不含扩展名）作为前缀
            input_name = Path(input_path).stem

            for i in range(num_pages):
                # 提取该页的姓名
                page = self._reader.pages[i]
                name = self._extract_name_from_resume(page)

                if not name:
                    name = f"{input_name}_第{i+1}页"

                # 生成安全的文件名
                safe_name = self._sanitize_filename(name)

                # 如果文件名重复，添加序号
                pdf_path = Path(output_dir) / f"{safe_name}.pdf"
                counter = 1
                while pdf_path.exists():
                    pdf_path = Path(output_dir) / f"{safe_name}_{counter}.pdf"
                    counter += 1

                # 提取单页 PDF
                self._extract_single_page(i, str(pdf_path))

                if progress_callback:
                    progress_callback(i + 1, num_pages, name)

            return True

        except Exception as e:
            import traceback
            print(f"拆分 PDF 失败：{e}")
            traceback.print_exc()
            if progress_callback:
                progress_callback(0, 0, f"错误: {e}")
            return False

    def _extract_name_from_resume(self, page) -> Optional[str]:
        """
        从简历表页面提取姓名
        简历表格式：姓 名 [姓名值] 性别
        """
        text = page.extract_text()
        if not text:
            return None

        # 清理文本
        text = text.replace('\x00', '')

        # 按空格分割词
        words = text.split()

        # 找到"姓"+"名"的组合
        for i in range(len(words) - 1):
            if words[i] == '姓' and words[i + 1] == '名':
                # "姓名"后面是姓名值，收集直到遇到中文表头词
                name_parts = []
                j = i + 2
                while j < len(words):
                    word = words[j]
                    # 遇到中文表头词就停止
                    if self._is_header_word(word):
                        break
                    # 跳过英文字段名
                    if self._is_english_field(word):
                        j += 1
                        continue
                    name_parts.append(word)
                    j += 1

                if name_parts:
                    # 合并姓名部分（保留空格和·符号）
                    name = ''.join(name_parts)
                    # 清理多余的空格但保留·符号
                    name = ' '.join(name.split())  # 规范化空格
                    if '·' in name:
                        # 保留·符号格式
                        name = name.replace(' ', '')  # 有·时去掉空格
                    if len(name) >= 1:
                        return name
                break

        return None

    def _is_header_word(self, word: str) -> bool:
        """检查是否为中文表头词"""
        header_set = {
            '性别', '民族', '出生', '政治', '学历', '学位',
            '籍贯', '入党', '入伍', '参加', '工作', '职务', '岗位',
            '简历', '主要', '家庭', '奖惩', '培训', '证书', '职位',
            '时间', '单位', '学习', '担任', '现', '曾', '在', '至',
            '简历表', '个人简历'
        }
        return word in header_set

    def _is_english_field(self, word: str) -> bool:
        """检查是否为英文字段名"""
        # 已知的英文字段名
        fields = {
            'xingbie', 'chushen', 'minzu', 'gangweizhiwu',
            'xueli', 'xuewei', 'ruwugong', 'zhiwu', 'rudang', 'gongzuo',
            'jianli', 'zhiwucengjiji', 'junxianjishijian'
        }
        return word.lower() in fields

    def _sanitize_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        # 移除或替换非法字符
        safe = re.sub(r'[\\/:*?"<>|]', '', filename)
        safe = safe.strip(' .')
        # 限制长度
        if len(safe) > 50:
            safe = safe[:50]
        return safe if safe else "未命名"

    def _extract_single_page(self, page_index: int, output_path: str) -> None:
        """提取单个页面到 PDF 文件"""
        writer = PdfWriter()
        writer.add_page(self._reader.pages[page_index])

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        writer.write(output_path)


def split_pdf_to_single_pages(
    input_path: str,
    output_dir: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> bool:
    """
    便捷函数：将 PDF 按页拆分为单页 PDF

    Args:
        input_path: 输入 PDF 文件路径
        output_dir: 输出目录
        progress_callback: 进度回调函数

    Returns:
        是否成功
    """
    splitter = PDFPageSplitter()
    return splitter.split_to_single_pages(input_path, output_dir, progress_callback)
