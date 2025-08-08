from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QDesktopWidget
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QFont

class FloatingWindow(QWidget):
    """
    一个精简的、可拖动的悬浮窗口，用于显示最后的倒计时。
    """
    closed = pyqtSignal()

    def __init__(self, position="top_right", size_scale=1.0, parent=None):
        super().__init__(parent)
        
        self.position_key = position
        self.size_scale = size_scale
        
        # 设置窗口属性
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |    # 保持在顶部
            Qt.FramelessWindowHint |    # 无边框
            Qt.Tool                     # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground) # 设置背景透明
        
        # --- Size ---
        base_width = 150
        base_height = 60
        self.setFixedSize(int(base_width * self.size_scale), int(base_height * self.size_scale))

        self.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(0, 0, 0, 180);
                border-radius: {10 * self.size_scale}px;
                color: white;
            }}
        """)
        
        # 创建UI组件
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.time_label = QLabel("00:59", self)
        font = QFont("Arial", int(24 * self.size_scale), QFont.Bold)
        self.time_label.setFont(font)
        self.time_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.time_label)
        
        self._drag_start_position = QPoint()
        self._set_initial_position()

    def _set_initial_position(self):
        screen_geometry = QDesktopWidget().screenGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        width = self.width()
        height = self.height()
        margin = 20 # 边距

        positions = {
            "top_right": QPoint(screen_width - width - margin, margin),
            "top_left": QPoint(margin, margin),
            "bottom_right": QPoint(screen_width - width - margin, screen_height - height - margin),
            "bottom_left": QPoint(margin, screen_height - height - margin),
            "center": QPoint((screen_width - width) // 2, (screen_height - height) // 2),
            "left_center": QPoint(margin, (screen_height - height) // 2),
            "right_center": QPoint(screen_width - width - margin, (screen_height - height) // 2)
        }
        
        self.move(positions.get(self.position_key, positions["top_right"]))

    def update_time(self, time_str: str):
        """更新显示的时间"""
        self.time_label.setText(time_str)

    def mousePressEvent(self, event):
        """记录鼠标按下的位置，用于窗口拖动"""
        if event.button() == Qt.LeftButton:
            self._drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """根据鼠标移动来移动窗口"""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start_position)
            event.accept()

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.closed.emit()
        super().closeEvent(event)
