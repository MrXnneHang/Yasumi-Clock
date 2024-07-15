import sys
from PyQt5 import QtCore, QtWidgets

from PyQt5.QtGui import QPixmap, QImage
from qfluentwidgets import PrimaryPushButton

import numpy as np
from PIL import Image

from util import load_config
from MainWindowThread import DrawAnimationThread

class Main_Window_UI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.window_config = load_config("./yasumi_config.yml")
        self.src_config = load_config("./src.yml")

        # Window pos
        self.main_window = self.window_config["yasumi_clock"]["main_window"]
        self.main_window_pos = self.main_window["window_pos"]
        self.draw_button_pos = self.main_window["start_draw"]
        self.start_fanqie_pos = self.main_window["start_fanqie"]
        self.animation_pos = self.main_window["animation"]
        self.timer_pos = self.main_window["timer"]
        self.addTime_pos = self.main_window["add_time"]
        self.subTime_pos = self.main_window["sub_time"]
        self.setTime_pos = self.main_window["set_time"]
        self.resetTime_pos = self.main_window["reset_time"]

        # Image Source
        self.example_img_path = self.src_config["example"]
        self.animation_play_path = self.src_config["play"]
        self.animation_work_path = self.src_config["work"]
        self.animation_path = self.animation_play_path

        self.animation_play_thread = None
        self.animation_work_thread = None


        # Init UI
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Main Window')
        self.setGeometry(self.main_window_pos[0], self.main_window_pos[1],
                          self.main_window_pos[2], self.main_window_pos[3])


        # Buttons
        self.startdrawButton = PrimaryPushButton('Draw Main Window', self)
        self.startdrawButton.setGeometry(QtCore.QRect(self.draw_button_pos[0],
                                                      self.draw_button_pos[1],
                                                      self.draw_button_pos[2],
                                                      self.draw_button_pos[3]))
        self.startFanqieButton = PrimaryPushButton('Start', self)
        self.startFanqieButton.setGeometry(QtCore.QRect(self.start_fanqie_pos[0],
                                                        self.start_fanqie_pos[1],
                                                        self.start_fanqie_pos[2],
                                                        self.start_fanqie_pos[3]))
        self.addTimeButton = PrimaryPushButton('➕',self)
        self.addTimeButton.setGeometry(QtCore.QRect(self.addTime_pos[0],
                                                    self.addTime_pos[1],
                                                    self.addTime_pos[2],
                                                    self.addTime_pos[3]))
        self.subTimeButton = PrimaryPushButton('➖',self)
        self.subTimeButton.setGeometry(QtCore.QRect(self.subTime_pos[0],
                                                    self.subTime_pos[1],
                                                    self.subTime_pos[2],
                                                    self.subTime_pos[3]))
        self.resetTimeButton = PrimaryPushButton('Rest',self)
        self.resetTimeButton.setGeometry(QtCore.QRect(self.resetTime_pos[0],
                                                      self.resetTime_pos[1],
                                                      self.resetTime_pos[2],
                                                      self.resetTime_pos[3]))


        # Labels
        self.animation_label = QtWidgets.QLabel(self)
        self.animation_label.setGeometry(QtCore.QRect(self.animation_pos[0],
                                                      self.animation_pos[1],
                                                      self.animation_pos[2],
                                                      self.animation_pos[3]))
        # 创建显示倒计时的标签
        self.timeLabel = QtWidgets.QLabel("00:00", self)
                # Set font size, weight, and color using RGBA
        self.timeLabel.setStyleSheet("""
            QLabel {
                font-size: 30px;
                font-weight: bold;
                color: rgba(0, 0, 0, 1);  /* White color */
                padding: 10px;
                border-radius: 5px;
                font-family: Arial;  /* 设置字体为 Arial */
                                     
            }
        """)
        self.timeLabel.setGeometry(QtCore.QRect(self.timer_pos[0],
                                                self.timer_pos[1],
                                                self.timer_pos[2],
                                                self.timer_pos[3]))

        self.setTimeLabel = QtWidgets.QLabel(self)
                # Set font size, weight, and color using RGBA
        self.setTimeLabel.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: bold;
                color: rgba(0, 0, 0, 1);  /* White color */
                padding: 10px;
                border-radius: 5px;
                font-family: Arial;  /* 设置字体为 Arial */
                                     
            }
        """)
        self.setTimeLabel.setGeometry(QtCore.QRect(self.setTime_pos[0],
                                                   self.setTime_pos[1],
                                                   self.setTime_pos[2],
                                                   self.setTime_pos[3]))

        # Start thread to draw GIF frames

        # self.Draw_Image(Label=self.animation_label,
        #                 path=self.example_img_path,
        #                 Pos=self.animation_pos)

        



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

