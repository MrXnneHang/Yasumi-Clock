import sys
from PyQt5 import QtCore, QtWidgets

from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QPushButton
import numpy as np
from PIL import Image

from util import load_config,set_pos
from MainWindowThread import DrawAnimationThread

class Main_Window_UI(QtWidgets.QWidget):
    """主窗口的UI布局

    属性:
    self.animation_play_thread:播放play动画的线程
    self.animation_work_thread:播放work动画的线程
    
    用法:
    作为Main UI Response的父类
    """
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.window_config = load_config(self.config["window_pos"])
        self.src_config = load_config(self.config["source"])

        # Window pos
        self.main_window = self.window_config["yasumi_clock"]["main_window"]
        self.main_window_pos = self.main_window["window_pos"]
        self.draw_button_pos = self.main_window["start_draw"]
        self.start_fanqie_pos = self.main_window["start_fanqie"]
        self.history_button_pos = self.main_window["history"]
        self.animation_pos = self.main_window["animation"]
        self.timer_pos = self.main_window["timer"]
        self.addTime_pos = self.main_window["add_time"]
        self.subTime_pos = self.main_window["sub_time"]
        self.setTime_pos = self.main_window["set_time"]
        self.resetTime_pos = self.main_window["reset_time"]

        # Image Source
        self.animation_play_path = self.src_config["play"]
        self.animation_work_path = self.src_config["work"]
        self.animation_path = self.animation_play_path

        self.animation_play_thread = None
        self.animation_work_thread = None

        # qss
        self.button_qss =  f"""
        QPushButton {{
            background-color: #1E90FF; /* 蓝色 */
            color: white;
            border: none;
            border-radius: {int(10)}px;
            padding: {int(5)}px {int(8)}px;
            font-size: {int(12)}px;
            font-weight: bold;
            font-family: Arial;
        }}

        QPushButton:hover {{
            background-color: #1C86EE; /* 略微深一点的蓝色 */
        }}

        QPushButton:pressed {{
            background-color: #1874CD; /* 更深的蓝色 */
        }}

        QPushButton:disabled {{
            background-color: #A9A9A9; /* 灰色 */
            color: #FFFFFF; /* 白色 */
        }}
        """


        # Init UI
        self.initUI()



    def initUI(self):
        self.setWindowTitle('Yasumi Clock v1.2')
        set_pos(self.main_window_pos,self)


        # Buttons
        self.startdrawButton = QPushButton('布局', self)
        set_pos(self.draw_button_pos,self.startdrawButton)
        self.startdrawButton.setStyleSheet(self.button_qss)

        self.startFanqieButton = QPushButton('Start', self)
        set_pos(self.start_fanqie_pos,self.startFanqieButton)
        self.startFanqieButton.setStyleSheet(self.button_qss)

        self.addTimeButton = QPushButton('+',self)
        set_pos(self.addTime_pos,self.addTimeButton)
        self.addTimeButton.setStyleSheet(self.button_qss)

        self.subTimeButton = QPushButton('-',self)
        set_pos(self.subTime_pos,self.subTimeButton)
        self.subTimeButton.setStyleSheet(self.button_qss)
        
        self.resetTimeButton = QPushButton('Rest',self)
        set_pos(self.resetTime_pos,self.resetTimeButton)
        self.resetTimeButton.setStyleSheet(self.button_qss)

        self.history_button = QPushButton('历史',self)
        set_pos(self.history_button_pos,self.history_button)
        self.history_button.setStyleSheet(self.button_qss)



        # Labels
        self.animation_label = QtWidgets.QLabel(self)
        set_pos(self.animation_pos,self.animation_label)
        # 创建显示倒计时的标签
        self.timeLabel = QtWidgets.QLabel("00:00", self)
        # Set font size, weight, and color using RGBA
        self.timeLabel.setStyleSheet(f"""
            QLabel {{
                font-size: {int(30)}px;
                font-weight: bold;
                color: rgba(0, 0, 0, 1);  /* White color */
                padding: {int(10)}px;
                border-radius: {int(5)}px;
                font-family: Arial;  /* 设置字体为 Arial */
                                     
            }}
        """)
        set_pos(self.timer_pos,self.timeLabel)
        self.setTimeLabel = QtWidgets.QLabel(self)
                # Set font size, weight, and color using RGBA
        self.setTimeLabel.setStyleSheet(f"""
            QLabel {{
                font-size: {int(15)}px;
                font-weight: bold;
                color: rgba(0, 0, 0, 1);  /* White color */
                padding: {int(10)}px;
                border-radius: {int(5)}px;
                font-family: Arial;  /* 设置字体为 Arial */
                                     
            }}
        """)
        set_pos(self.setTime_pos,self.setTimeLabel)


        



    def onMainWindowShow(self):
        # 当 mainWindow 显示时调用此槽函数
        if hasattr(self, 'loading_window') and self.loading_window.isVisible():
            self.loading_window.close()
 
    def Draw_Image(self,Label,Pos,path=None,frame=None):

        img = Image.open(path)
        img = img.resize((Pos[2],Pos[3]),Image.BILINEAR)
        img = np.array(img)
        rgb_image = img

        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        Label.setPixmap(pixmap)
    def start_drawgif_task(self,action):
        if action == "play":
            if not self.animation_play_thread or not self.animation_play_thread.isRunning():
                self.animation_play_thread = DrawAnimationThread()
                self.animation_play_thread.setup(path=self.animation_path,
                                label=self.animation_label,
                                pos=self.animation_pos,
                                frame_speed=30)
                self.animation_play_thread.start()
        elif action == "work":
            if not self.animation_work_thread or not self.animation_work_thread.isRunning():
                self.animation_work_thread = DrawAnimationThread()
                self.animation_work_thread.setup(path=self.animation_path,
                                label=self.animation_label,
                                pos=self.animation_pos,
                                frame_speed=30)
                self.animation_work_thread.start()

