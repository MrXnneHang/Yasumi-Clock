import sys
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout, QMainWindow

from PyQt5.QtCore import Qt
from util import load_config
from MainWindowThread import DrawAnimationThread


# 定义加载窗口类
class yasumiWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.windowconfig = load_config("./yasumi_config.yml")
        self.src_conifg = load_config("./src.yml")
        self.desktop = QApplication.desktop()
        self.gif = self.src_conifg["yasumi"]
 
        # 获取显示器分辨率大小
        self.screenRect = self.desktop.screenGeometry()
        self.screen_height = self.screenRect.height()
        self.screen_width = self.screenRect.width()

        self.yasumi_thread = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Loading...")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(self.screen_width // 6 * 5,
                          self.screen_height // 6 * 5)  # 固定窗口大小
        self.setStyleSheet("background-color: white;")  # 设置背景色为白色
        
        # 隐藏最小化，关闭等按键
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint|Qt.WindowStaysOnTopHint)
        self.animation_label = QLabel(self)
        self.animation_label.setGeometry(QtCore.QRect(0 ,
                                                      0,
                                                      self.screen_width // 6 * 5,
                                                      self.screen_height // 6 * 5))
        self.start_drawgif_task()

    def start_drawgif_task(self):
        if not self.yasumi_thread or not self.yasumi_thread.isRunning():
            self.yasumi_thread = DrawAnimationThread()
            self.yasumi_thread.setup(path=self.gif,
                                     label=self.animation_label,
                                     pos=(0,
                                          0,
                                          self.screen_width // 6 * 5,
                                          self.screen_height // 6 * 5),
                                     frame_speed=24,
                                     whileTrue=False)
            self.yasumi_thread.start()

    def closeEvent(self, event):
        if self.yasumi_thread and self.yasumi_thread.isRunning():
            self.yasumi_thread.running = False
            self.yasumi_thread.wait()
            self.yasumi_thread.quit()
        event.accept()