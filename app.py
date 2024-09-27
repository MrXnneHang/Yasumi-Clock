import sys
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer, QTime, Qt
from PyQt5.QtGui import QPixmap, QImage,QIcon

import numpy as np
import threading
from PIL import Image
from time import sleep
import datetime


from util import load_config,split_gif_to_frames,date_scrollation
from yasumi_draw_rec import ManualSelectionWindow
from MainWindowThread import DrawAnimationThread
from LoadingWindow import LoadingWindow
from yasumi_window import yasumiWindow
from MainWindowUI import Main_Window_UI
from sqlite import init_db,add_focus_record
from history_window import HistoryWindowUI

class Main_Window_Response(Main_Window_UI):
    """主窗口的响应

    属性:
    self.timer:更新倒计时,每秒一次。
    self.CloseYausmi:定时五分钟关闭Yausmi Window
    self.total_time:这一次要计时的时长
    self.time_index:加减时长

    函数:
    list_main_button_pos:返回要复刻的Buttons。
    showDrawMainWindow:新建窗口复刻main Window布局,并且打印画矩形的x,y,w,h
    Show:关闭加载窗口,打开主窗口
    change_animation(action):将播放动画指定为action(play/work)
    """
    def __init__(self,loading_window):
        super().__init__()
        self.startdrawButton.clicked.connect(self.showDrawMainWindow)
        self.startFanqieButton.clicked.connect(self.startFanqie)
        self.addTimeButton.clicked.connect(self.add_time)
        self.subTimeButton.clicked.connect(self.sub_time)
        self.resetTimeButton.clicked.connect(self.resetTime)
        self.history_button.clicked.connect(self.showHistoryWindow)
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
        self.set_time = 0
        self.total_focuse_time = 0

        self.timerRunning = False
        self.start_drawgif_task(action="play")

        init_db()

    
    def change_animation(self,action):
        if action == "work":
            if self.animation_play_thread and self.animation_play_thread.isRunning():
                self.animation_play_thread.running = False
                self.animation_play_thread.wait()
                self.animation_play_thread.quit()
                self.animation_path = self.animation_work_path
                self.start_drawgif_task(action="work")
        elif action == "play":
            if self.animation_work_thread and self.animation_work_thread.isRunning():
                self.animation_work_thread.running = False
                self.animation_work_thread.wait()
                self.animation_work_thread.quit()
                self.animation_path = self.animation_play_path
                self.start_drawgif_task(action="play")

    
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
        self.change_animation(action="play")
        self.timerRunning = False
        self.timer.stop()
        self.timeLabel.setText("Reset")

            


    def showHistoryWindow(self):
        self.history_window = HistoryWindowUI()
        self.history_window.setWindowIcon(QIcon(mainWindow.src_config["icon"]))
        self.history_window.show_week_report()
        self.history_window.show_habbit_report()
        self.history_window.show()
    def showDrawMainWindow(self):
        child_window_pos = self.list_main_button_pos()
        self.selectionWindow = ManualSelectionWindow(self.main_window_pos,child_window_pos)
        self.selectionWindow.setWindowIcon(QIcon(mainWindow.src_config["icon"]))
        self.selectionWindow.show()
    def startFanqie(self):
        if not self.timerRunning:
            self.change_animation(action="work")
            self.startCountdown(self.total_time[self.time_index])
            self.timerRunning = True
            self.set_time = self.time_index * 5
        else:
            print("已经有计时器在运行")
            pass
       

    
    def startCountdown(self,time_str):

        try:
            # 将输入的时间字符串分割成分钟和秒数
            minutes, seconds = map(int, time_str.split(':'))
            # 设置剩余时间
            self.timeRemaining = QTime(0, minutes, seconds)
            # 启动计时器,每秒更新一次
            self.timer.start(1000)
        except ValueError:
            # 如果输入的时间格式无效,则显示错误信息
            self.timeLabel.setText("Invalid time format!")

    def updateTimer(self):
        if self.timeRemaining == QTime(0, 0):
            self.timer.stop()
            self.timeLabel.setText("End!")
            self.timerRunning = False
            print("You Have focused for {} minutes".format(self.set_time))
            add_focus_record(self.set_time)
            self.yasumi = yasumiWindow()
            self.yasumi.setWindowIcon(QIcon(mainWindow.src_config["icon"]))
            self.yasumi.show()
            self.change_animation(action="play")
            self.closeYasumi.singleShot(5*60*1000,self.yasumi.close)
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
                self.resetTime_pos,self.setTime_pos,self.history_button_pos
                ]
    def closeEvent(self, event):
        """退出程序"""
        print("退出程序")
        event.accept()
        sys.exit()
    



if __name__ == '__main__':
    QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    

    loading_window = LoadingWindow()
    mainWindow = Main_Window_Response(loading_window)
    mainWindow.setWindowIcon(QIcon(mainWindow.src_config["icon"]))
    loading_window.setWindowIcon(QIcon(mainWindow.src_config["icon"]))
    loading_window.show()
    # mainWindow.show()

    timer = QtCore.QTimer()
    timer.singleShot(1500, mainWindow.Show)  # Delay mainWindow's show by 1 second
    

    sys.exit(app.exec_())