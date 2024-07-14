import sys
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer, QTime
from PyQt5.QtGui import QPixmap, QImage,QIcon
from qfluentwidgets import PrimaryPushButton

import numpy as np
import threading
from PIL import Image
from time import sleep


from util import load_config,split_gif_to_frames
from yasumi_draw_rec import ManualSelectionWindow
from MainWindowThread import DrawAnimationThread
from LoadingWindow import LoadingWindow
from yasumi_window import yasumiWindow
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
        self.example_gif_path = self.src_config["example_gif"]

        self.animation_thread = None

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

        self.start_drawgif_task()
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
    def start_drawgif_task(self):
        if not self.animation_thread or not self.animation_thread.isRunning():
            self.animation_thread = DrawAnimationThread()
            self.animation_thread.setup(path=self.example_gif_path,
                                              label=self.animation_label,
                                              pos=self.animation_pos,
                                              frame_speed=12)
            self.animation_thread.start()



class Main_Window_Response(Main_Window_UI):
    def __init__(self,loading_window):
        super().__init__()
        self.startdrawButton.clicked.connect(self.showDrawMainWindow)
        self.startFanqieButton.clicked.connect(self.startFanqie)
        self.addTimeButton.clicked.connect(self.add_time)
        self.subTimeButton.clicked.connect(self.sub_time)
        self.resetTimeButton.clicked.connect(self.resetTime)
        self.loadingwindow = loading_window

        self.timeRemaining = QTime(0,0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateTimer)
        self.closeYasumi = QTimer(self)
        

        self.timeLabel.setText("Begin!")
        self.total_time = ["00:00","05:00","10:00",
                           "15:00","20:00","25:00",
                           "30:00","35:00","40:00"]
        self.time_index = 4
        self.setTimeLabel.setText(self.total_time[self.time_index])

        self.timerRunning = False

    
    def add_time(self):
        if self.time_index < 8:
            self.time_index += 1
            self.setTimeLabel.setText(self.total_time[self.time_index])
        else:
            pass
    def sub_time(self):    
        if self.time_index > 0:
            self.time_index -= 1
            self.setTimeLabel.setText(self.total_time[self.time_index])
        else:
            pass
    def resetTime(self):
        self.timerRunning = False
        self.timer.stop()
        self.timeLabel.setText("Reset")


    def showDrawMainWindow(self):
        child_window_pos = self.list_main_button_pos()
        self.selectionWindow = ManualSelectionWindow(self.main_window_pos,child_window_pos)
        self.selectionWindow.show()
    def startFanqie(self):
        if not self.timerRunning:
            self.startCountdown(self.total_time[self.time_index])
            self.timerRunning = True
        else:
            print("已经有计时器在运行")
            pass
       

    
    def startCountdown(self,time_str):

        try:
            # 将输入的时间字符串分割成分钟和秒数
            minutes, seconds = map(int, time_str.split(':'))
            # 设置剩余时间
            self.timeRemaining = QTime(0, minutes, seconds)
            # 启动计时器，每秒更新一次
            self.timer.start(1000)
        except ValueError:
            # 如果输入的时间格式无效，则显示错误信息
            self.timeLabel.setText("Invalid time format!")

    def updateTimer(self):
        if self.timeRemaining == QTime(0, 0):
            self.timer.stop()
            self.timeLabel.setText("End!")
            self.yasumi = yasumiWindow()
            self.yasumi.show()
            self.timerRunning = False
            self.closeYasumi.singleShot(5000,self.yasumi.close)
        else:
            self.timeRemaining = self.timeRemaining.addSecs(-1)
            self.timeLabel.setText(self.timeRemaining.toString("mm:ss"))

    def Show(self):
        self.show()
        if self.loadingwindow:
            self.loadingwindow.close()

    def list_main_button_pos(self):
        return [self.draw_button_pos,self.start_fanqie_pos,self.animation_pos,
                self.timer_pos,self.addTime_pos,self.subTime_pos,
                self.resetTime_pos,self.setTime_pos
                ]



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    
    #loading_window = LoadingWindow()
    #loading_window.show()

    mainWindow = Main_Window_Response(None)
    mainWindow.setWindowIcon(QIcon(mainWindow.src_config["icon"]))
    mainWindow.show()

    #timer = QtCore.QTimer()
    #timer.singleShot(1500, mainWindow.Show)  # Delay mainWindow's show by 1 second
    

    sys.exit(app.exec_())