import sys
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout, QMainWindow

from PyQt5.QtCore import Qt
from util import load_config
from MainWindowThread import DrawAnimationThread
# 定义加载窗口类
class LoadingWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.windowconfig = load_config("./yasumi_config.yml")
        self.src_conifg = load_config("./src.yml")
        self.LoadingWindow = self.windowconfig["yasumi_clock"]["LoadingWindow"]

        self.animation_thread = None
        self.initUI()
    def initUI(self):
        self.setWindowTitle("Loading...")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(self.LoadingWindow["window_pos"][0],
                          self.LoadingWindow["window_pos"][1])  # 固定窗口大小
        self.setStyleSheet("background-color: white;")  # 设置背景色为白色
        
        # 隐藏最小化，关闭等按键
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint|Qt.WindowStaysOnTopHint)  # 设置窗口标志位
        self.animation_label = QLabel(self)
        self.animation_label.setGeometry(QtCore.QRect(self.LoadingWindow["animation"][0],
                                                      self.LoadingWindow["animation"][1],
                                                      self.LoadingWindow["animation"][2],
                                                      self.LoadingWindow["animation"][3]))
        self.start_drawgif_task()


    def start_drawgif_task(self):
        if not self.animation_thread or not self.animation_thread.isRunning():
            self.animation_thread = DrawAnimationThread()
            self.animation_thread.setup(path=self.src_conifg["loading"],
                                              label=self.animation_label,
                                              pos=self.LoadingWindow["animation"],
                                              frame_speed=24)
            self.animation_thread.start()
    
    def closeEvent(self, event):
        if self.animation_thread and self.animation_thread.isRunning():
            self.animation_thread.running = False
            self.animation_thread.wait()
            self.animation_thread.quit()
        event.accept()
