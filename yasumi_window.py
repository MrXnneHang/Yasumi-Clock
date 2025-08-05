import sys
import os
from pathlib import Path
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout, QMainWindow

from PyQt5.QtCore import Qt
from util import load_config,combine_path,get_absolute_dir
from MainWindowThread import DrawAnimationThread


class yasumiWindow(QDialog):
    """倒计时结束后的休息窗口，播放一遍麻衣学姐的gif。

    self.yasumi_thread:播放动画的Qthread
    """
    def __init__(self, main_window_ref):
        super().__init__()
        self.main_window_ref = main_window_ref
        self.absolute_dir = get_absolute_dir()

        self.windowconfig = load_config(self.absolute_dir / "yasumi_config.yml")
        self.src_conifg = load_config(self.absolute_dir / "src.yml")
        self.force_rest = self.windowconfig["yasumi_clock"].get("force_rest", False)
        self.desktop = QApplication.desktop()
        self.gif = combine_path(self.absolute_dir,self.src_conifg["yasumi"])
 
        # 获取显示器分辨率大小
        self.screenRect = self.desktop.screenGeometry()
        self.screen_height = self.screenRect.height()
        self.screen_width = self.screenRect.width()

        self.yasumi_thread = None
        self._allow_close = False  # 关键标志位，用于区分程序关闭和用户关闭
        self.initUI()

    def initUI(self):
        self.setWindowTitle("休息一下...")
        if self.force_rest:
            # 强制模式：无边框，置顶，并且作为工具窗口（不在任务栏显示）
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.Tool)
        else:
            # 非强制模式：标准对话框，置顶
            self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)

        self.setFixedSize(self.screen_width // 6 * 5,
                          self.screen_height // 6 * 5)  # 固定窗口大小
        self.setStyleSheet("background-color: white;")  # 设置背景色为白色
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
        # 当用户尝试关闭窗口 (如 AltF4) 或程序调用 close() 时触发
        if self.force_rest and not self._allow_close:
            print("强制休息模式开启，无法关闭此窗口。")
            event.ignore()  # 忽略关闭事件
        else:
            # 如果是非强制模式，或由程序触发的关闭，则允许关闭
            if self.yasumi_thread and self.yasumi_thread.isRunning():
                self.yasumi_thread.running = False
                self.yasumi_thread.wait()
                self.yasumi_thread.quit()
            if hasattr(self, 'main_window_ref') and self.main_window_ref.isHidden():
                self.main_window_ref.on_yasumi_closed()
                
            event.accept()  # 接受关闭事件

    def close(self):
        """重写 close() 方法，在程序调用时设置允许关闭的标志。"""
        self._allow_close = True
        super().close()