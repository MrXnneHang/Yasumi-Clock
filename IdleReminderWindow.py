from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt

class IdleReminderWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        self.label = QLabel("已经休息很久了，\n要不要开始下一个专注时段？", self)
        self.label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180);
            color: white;
            font-size: 18px;
            padding: 20px;
            border-radius: 15px;
        """)
        layout.addWidget(self.label)

        self.close_button = QPushButton("知道了", self)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.2);
                color: white;
                border: 1px solid white;
                padding: 5px 15px;
                border-radius: 12px;
                font-size: 14px;
                margin-top: 5px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.4);
            }
        """)
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button, 0, Qt.AlignCenter)

    def mousePressEvent(self, event):
        # 点击窗口任意位置即可关闭
        self.close()