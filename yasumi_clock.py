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
                color: rgba(255, 255, 255, 1);  /* White color */
                background-color: rgba(52, 152, 219, 1);  /* Blue color */
                padding: 10px;
                border-radius: 5px;
            }
        """)
        self.timeLabel.setGeometry(QtCore.QRect(self.timer_pos[0],
                                                      self.timer_pos[1],
                                                      self.timer_pos[2],
                                                      self.timer_pos[3]))

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
        self.loadingwindow = loading_window
        self.timeRemaining = QTime(0,0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateTimer)
        self.timeLabel.setText("Begin!")
        

    def showDrawMainWindow(self):
        child_window_pos = self.list_main_button_pos()
        self.selectionWindow = ManualSelectionWindow(self.main_window_pos,child_window_pos)
        self.selectionWindow.show()
    def startFanqie(self):
        self.startCountdown("00:05")
       

    
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
        else:
            self.timeRemaining = self.timeRemaining.addSecs(-1)
            self.timeLabel.setText(self.timeRemaining.toString("mm:ss"))

    def Show(self):
        self.show()
        if self.loadingwindow:
            self.loadingwindow.close()

    def list_main_button_pos(self):
        return [self.draw_button_pos,self.start_fanqie_pos,self.animation_pos]



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