"""
预览组件 - PDF 文件预览和简单编辑
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QPushButton, QComboBox, QMessageBox, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QRectF, QSize, QEvent
from PySide6.QtGui import QFont, QPixmap, QImage

from pathlib import Path
from typing import Optional, List

from pypdf import PdfReader, PdfWriter


class PageThumbnail(QFrame):
    """PDF 页面缩略图"""

    def __init__(self, page_num: int, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self.original_pixmap = pixmap
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 3px;
                margin: 2px;
            }
            QFrame:hover {
                border-color: #0078d4;
                background-color: #f0f7ff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        # 页码标签
        self.page_label = QLabel(f"P{page_num + 1}")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setFont(QFont("Microsoft YaHei UI", 8))
        self.page_label.setStyleSheet("color: #666;")
        layout.addWidget(self.page_label)

        # 缩略图 - 使用 QLabel 并设置大小策略
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._update_pixmap(1.0)
        layout.addWidget(self.image_label)

    def _update_pixmap(self, scale: float) -> None:
        """更新缩略图显示"""
        if self.original_pixmap:
            # 显示时可以放大到 300%，但使用平滑缩放避免崩溃
            scaled = self.original_pixmap.scaled(
                int(self.original_pixmap.width() * scale),
                int(self.original_pixmap.height() * scale),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

    def set_scale(self, scale: float) -> None:
        """设置缩放比例"""
        self._update_pixmap(scale)

    def get_page_num(self) -> int:
        return self.page_num


class PreviewWidget(QWidget):
    """
    文件预览组件
    显示 PDF 页面缩略图和简单编辑功能
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self.pdf_reader = None
        self.page_widgets: List[PageThumbnail] = []
        self.current_scale = 1.0
        # 缩放范围为 50% - 300%
        self.zoom_levels = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
        self.current_zoom_index = 2  # 100%

        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 顶部工具栏
        self._create_toolbar(layout)

        # 滚动区域 - 显示页面缩略图
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # 启用鼠标滚轮缩放
        self.scroll_area.installEventFilter(self)

        # 内容容器
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.content_layout.setSpacing(8)

        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)

        # 初始提示
        self._show_empty_state()

    def _create_toolbar(self, layout: QVBoxLayout) -> None:
        """创建工具栏"""
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)

        # 标题和提示
        title_label = QLabel("📄 PDF 预览  |  Ctrl+ 滚轮缩放")
        title_label.setFont(QFont("Microsoft YaHei UI", 11, QFont.Bold))
        title_label.setStyleSheet("color: #0078d4;")
        toolbar_layout.addWidget(title_label)

        toolbar_layout.addStretch()

        # 页面选择
        toolbar_layout.addWidget(QLabel("页码:"))
        self.page_combo = QComboBox()
        self.page_combo.setMinimumWidth(80)
        self.page_combo.setMaxVisibleItems(15)
        self.page_combo.currentIndexChanged.connect(self._on_page_changed)
        toolbar_layout.addWidget(self.page_combo)

        # 缩放级别
        toolbar_layout.addWidget(QLabel("缩放:"))
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["50%", "75%", "100%", "125%", "150%", "200%", "250%", "300%"])
        self.zoom_combo.setCurrentIndex(2)
        self.zoom_combo.currentTextChanged.connect(self._on_zoom_changed)
        self.zoom_combo.setMinimumWidth(70)
        toolbar_layout.addWidget(self.zoom_combo)

        toolbar_layout.addStretch()

        # 删除页面按钮
        self.btn_delete_page = QPushButton("🗑️ 删除")
        self.btn_delete_page.setStyleSheet(self._get_button_style("#dc3545", "#c82333"))
        self.btn_delete_page.clicked.connect(self._delete_current_page)
        self.btn_delete_page.setEnabled(False)
        toolbar_layout.addWidget(self.btn_delete_page)

        # 旋转页面按钮
        self.btn_rotate_page = QPushButton("🔄 旋转")
        self.btn_rotate_page.setStyleSheet(self._get_button_style("#28a745", "#218838"))
        self.btn_rotate_page.clicked.connect(self._rotate_current_page)
        self.btn_rotate_page.setEnabled(False)
        toolbar_layout.addWidget(self.btn_rotate_page)

        # 保存按钮
        self.btn_save = QPushButton("💾 保存")
        self.btn_save.setStyleSheet(self._get_button_style("#0078d4", "#106ebe"))
        self.btn_save.clicked.connect(self._save_changes)
        self.btn_save.setEnabled(False)
        toolbar_layout.addWidget(self.btn_save)

        layout.addLayout(toolbar_layout)

    def _get_button_style(self, color: str, hover_color: str) -> str:
        """获取按钮样式"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
            }}
        """

    def _show_empty_state(self) -> None:
        """显示空状态提示"""
        self._clear_content()

        label = QLabel("请从左侧选择一个 PDF 文件\n提示：按 Ctrl+ 滚轮可缩放预览图")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: gray; font-size: 11px;")
        self.content_layout.addWidget(label)

    def _clear_content(self) -> None:
        """清空内容"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.page_widgets = []

    def show_file(self, file_path: str) -> None:
        """显示文件预览"""
        self.current_file = file_path
        self._clear_content()
        self.page_combo.clear()

        # 重置按钮状态
        self.btn_delete_page.setEnabled(False)
        self.btn_rotate_page.setEnabled(False)
        self.btn_save.setEnabled(False)

        if not file_path or not str(file_path).strip():
            self._show_empty_state()
            return

        path = Path(file_path)

        if not path.exists():
            self._show_error(f"文件不存在：{file_path}")
            return

        if path.suffix.lower() != '.pdf':
            self._show_error("仅支持 PDF 文件预览")
            return

        self._show_pdf_preview(path)

    def _show_error(self, message: str) -> None:
        """显示错误信息"""
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: red; font-size: 11px;")
        self.content_layout.addWidget(label)

    def _show_pdf_preview(self, path: Path) -> None:
        """显示 PDF 页面缩略图"""
        try:
            self.pdf_reader = PdfReader(str(path))
            num_pages = len(self.pdf_reader.pages)

            # 生成页面缩略图
            self._generate_thumbnails(path, num_pages)

            # 填充页面选择框
            for i in range(num_pages):
                self.page_combo.addItem(f"P{i + 1}")

            # 启用编辑按钮
            if num_pages > 0:
                self.btn_delete_page.setEnabled(True)
                self.btn_rotate_page.setEnabled(True)

        except Exception as e:
            self._show_error(f"读取 PDF 失败：{e}")

    def _generate_thumbnails(self, path: Path, num_pages: int) -> None:
        """生成 PDF 页面缩略图"""
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(str(path))
            self.current_scale = self.zoom_levels[self.current_zoom_index]

            for i in range(num_pages):
                page = pdf[i]
                # 渲染时使用 1.0 基础缩放，避免大图崩溃
                # 显示时再缩放到目标大小
                pil_image = page.render(scale=1.0).to_pil()
                pixmap = QPixmap.fromImage(
                    QImage(
                        pil_image.tobytes("raw", "RGB"),
                        pil_image.width,
                        pil_image.height,
                        QImage.Format_RGB888
                    )
                )
                thumbnail = PageThumbnail(i, pixmap)
                # 设置初始缩放
                thumbnail.set_scale(self.current_scale)
                self.page_widgets.append(thumbnail)
                self.content_layout.addWidget(thumbnail)

            pdf.close()
        except ImportError as e:
            self._show_error(f"pypdfium2 加载失败：{e}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_error(f"生成缩略图失败：{e}")

    def eventFilter(self, obj, event) -> bool:
        """事件过滤器 - 处理鼠标滚轮缩放"""
        if event.type() == QEvent.Wheel and obj == self.scroll_area:
            if event.modifiers() == Qt.ControlModifier:
                # Ctrl+ 滚轮缩放
                delta = event.angleDelta().y()
                if delta > 0:
                    self._zoom_in()
                else:
                    self._zoom_out()
                return True
        return super().eventFilter(obj, event)

    def _zoom_in(self) -> None:
        """放大"""
        if self.current_zoom_index < len(self.zoom_levels) - 1:
            self.current_zoom_index += 1
            self.zoom_combo.setCurrentIndex(self.current_zoom_index)

    def _zoom_out(self) -> None:
        """缩小"""
        if self.current_zoom_index > 0:
            self.current_zoom_index -= 1
            self.zoom_combo.setCurrentIndex(self.current_zoom_index)

    def _on_page_changed(self, index: int) -> None:
        """页面选择改变"""
        # 可以滚动到对应页面
        if 0 <= index < len(self.page_widgets):
            widget = self.page_widgets[index]
            self.scroll_area.ensureWidgetVisible(widget)

    def _on_zoom_changed(self, text: str) -> None:
        """缩放级别改变"""
        zoom_percent = int(text.replace('%', ''))
        self.current_scale = zoom_percent / 100.0
        self.current_zoom_index = self.zoom_combo.currentIndex()
        self._regenerate_thumbnails()

    def _regenerate_thumbnails(self) -> None:
        """重新生成缩略图"""
        if not self.current_file or not self.pdf_reader:
            return

        # 保存当前滚动位置
        scrollbar_value = self.scroll_area.verticalScrollBar().value()

        self._clear_content()
        path = Path(self.current_file)
        num_pages = len(self.pdf_reader.pages)
        self._generate_thumbnails(path, num_pages)

        # 恢复滚动位置
        self.scroll_area.verticalScrollBar().setValue(scrollbar_value)

    def _delete_current_page(self) -> None:
        """删除当前选中的页面"""
        current_index = self.page_combo.currentIndex()
        if current_index < 0:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除第 {current_index + 1} 页吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if not hasattr(self, '_pages_to_delete'):
                self._pages_to_delete = []
            self._pages_to_delete.append(current_index)
            self.btn_save.setEnabled(True)

    def _rotate_current_page(self) -> None:
        """旋转当前选中的页面"""
        current_index = self.page_combo.currentIndex()
        if current_index < 0:
            return

        if not hasattr(self, '_pages_to_rotate'):
            self._pages_to_rotate = {}

        current_rotation = self._pages_to_rotate.get(current_index, 0)
        self._pages_to_rotate[current_index] = (current_rotation + 90) % 360
        self.btn_save.setEnabled(True)

    def _save_changes(self) -> None:
        """保存修改"""
        if not self.current_file:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存修改后的 PDF",
            self.current_file,
            "PDF 文件 (*.pdf)"
        )

        if not save_path:
            return

        try:
            reader = PdfReader(self.current_file)
            writer = PdfWriter()

            pages_to_delete = getattr(self, '_pages_to_delete', [])
            pages_to_rotate = getattr(self, '_pages_to_rotate', {})

            for i, page in enumerate(reader.pages):
                if i in pages_to_delete:
                    continue

                if i in pages_to_rotate:
                    rotation = pages_to_rotate[i]
                    page.rotate(rotation)

                writer.add_page(page)

            writer.write(save_path)

            self._pages_to_delete = []
            self._pages_to_rotate = {}
            self.btn_save.setEnabled(False)

            QMessageBox.information(self, "保存成功", f"修改已保存到:\n{save_path}")

            self.current_file = save_path
            self._show_pdf_preview(Path(save_path))

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存 PDF 时出错:\n{e}")

    def clear(self) -> None:
        """清空预览"""
        self.current_file = None
        self.pdf_reader = None
        self._show_empty_state()
        self.btn_delete_page.setEnabled(False)
        self.btn_rotate_page.setEnabled(False)
        self.btn_save.setEnabled(False)
