import sys
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QPushButton
import numpy as np
from PIL import Image 
from util import load_config,set_pos,date_scrollation
from yasumi_draw_rec import ManualSelectionWindow
from sqlite import get_focus_records
import datetime
class HistoryWindowUI(QtWidgets.QWidget):
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
        
        # Window pos
        self.main_window = self.window_config["yasumi_clock"]["history_window"]
        self.main_window_pos = self.main_window["window_pos"]
        self.draw_button_pos = self.main_window["start_draw"]
        self.total_time_label_pos = self.main_window["total_time_label"]
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
        self.label_qss = f"""
            QLabel {{
                font-size: {int(24)}px;
                font-weight: bold;
                color: rgba(0, 0, 0, 1);  /* White color */
                padding: {int(10)}px;
                border-radius: {int(5)}px;
                font-family: Arial;  /* 设置字体为 Arial */
                                     
            }}
        """


        # Init UI
        self.initUI()
        self.startdrawButton.clicked.connect(self.showDrawMainWindow)

    def showDrawMainWindow(self):
        child_button_poses = self.list_main_button_pos()
        self.window1 = ManualSelectionWindow(self.main_window_pos,child_button_poses)
        self.window1.show()


    def list_main_button_pos(self):
        return [self.draw_button_pos,self.total_time_label_pos]
    
    def calculate_total_time(self):
        total_record_list = get_focus_records()
        total_time = 0
        for record in total_record_list:
            total_time += record["focus_time"]
        return total_time
    
    def weekly_report(self):
        """周报"""
        total_record_list = self.calculate_total_time()
        date = datetime.now().strftime("%Y-%m-%d")
        """从date往前推7天,可能跨月份,找出这7天的记录,记录的时间在record["date"]中,str,y-m-d-h,找出七天,如果不足七天,就不足七天,找出前n天(n<=7)"""
        focus_time = []
        for i in range(7):
            date = date_scrollation(date)
            daily_focus_time = 0
            daily_focus_count = 0
            for record in total_record_list:
                if date in record["date"]:
                    daily_focus_time += record["focus_time"]
                    daily_focus_count += 1
            focus_time.append((date,
                               daily_focus_time,
                               daily_focus_count,
                               int(daily_focus_time/daily_focus_count)))
        return focus_time
    def day_time_table(self):
        """习惯表，展示专注时间在一天中的分布，全局统计，可以看出时间段最经常专注"""
        total_record_list = self.calculate_total_time()
        focus_table = []
        for record in total_record_list:
            record["date"] = record["date"].split("-")[-1]
            focus_table.append(record)
        for i in range(24):
            focus_time = 0
            focus_count = 0
            for record in focus_table:
                if record["date"] == i:
                    focus_time += record["focus_time"]
                    focus_count += 1
            focus_table.append((i,focus_time,focus_count,int(focus_time/focus_count)))
        return focus_table

    def initUI(self):
        self.setWindowTitle('Yasumi Clock v1.2')
        set_pos(self.main_window_pos,self)
        # Buttons
        self.startdrawButton = QPushButton('布局', self)
        set_pos(self.draw_button_pos,self.startdrawButton)
        self.startdrawButton.setStyleSheet(self.button_qss)
        
        self.total_time_label = QtWidgets.QLabel("你专注了{}分钟,感谢对本软件是使用^-^/".format(self.calculate_total_time()), self)
        set_pos(self.total_time_label_pos,self.total_time_label)
        self.total_time_label.setStyleSheet(self.label_qss)