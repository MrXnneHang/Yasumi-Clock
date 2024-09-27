import sys
from PyQt5 import QtWidgets
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QPushButton
import numpy as np
from PIL import Image 
from util import load_config,set_pos
from yasumi_draw_rec import ManualSelectionWindow
from sqlite import calculate_total_time,weekly_report,day_time_table,plot_week_report,plot_focus_habit,get_focus_records
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
        self.habbit_label_pos = self.main_window["habbit_label"]
        self.week_report_pos = self.main_window["week_report_label"]
        self.text_label_pos = self.main_window["text_label"]
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
        self.lite_label_qss = f"""
            QLabel {{
                font-size: {int(16)}px;
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
        
    def Draw_Image(self, Label, Pos, path=None, frame=None):
        # Load image using PIL
        img = Image.open(path)

        # Resize the image
        img = img.resize((Pos[2], Pos[3]), Image.BILINEAR)

        # Convert to RGBA (to handle alpha channel)
        img = img.convert('RGBA')
        
        # Convert to NumPy array
        rgba_image = np.array(img)

        # Get image dimensions and channels
        h, w, ch = rgba_image.shape
        bytes_per_line = ch * w

        # Create QImage, now using Format_RGBA8888 to handle alpha channel
        q_img = QImage(rgba_image.data, w, h, bytes_per_line, QImage.Format_RGBA8888)

        # Convert to QPixmap and set it to the label
        pixmap = QPixmap.fromImage(q_img)
        Label.setPixmap(pixmap)
    def show_habbit_report(self):
        report = day_time_table()
        plot_focus_habit(report)
        self.Draw_Image(self.habbit_label,self.habbit_label_pos,path=self.config["habbit_image_path"])
    def show_week_report(self):
        report = weekly_report()
        plot_week_report(report)
        self.Draw_Image(self.week_report_label,self.week_report_pos,path=self.config["week_report_image_path"]) 
    def showDrawMainWindow(self):
        child_button_poses = self.list_main_button_pos()
        self.window1 = ManualSelectionWindow(self.main_window_pos,child_button_poses)
        self.window1.show()


    def list_main_button_pos(self):
        return [self.draw_button_pos,
                self.total_time_label_pos,
                self.habbit_label_pos,
                self.week_report_pos,
                self.text_label_pos]
    
    
    def initUI(self):
        self.setWindowTitle('Yasumi Clock v1.3')
        set_pos(self.main_window_pos,self)
        # Buttons
        self.startdrawButton = QPushButton('布局', self)
        set_pos(self.draw_button_pos,self.startdrawButton)
        self.startdrawButton.setStyleSheet(self.button_qss)
        
        if calculate_total_time()!=0:
            self.total_time_label = QtWidgets.QLabel("你专注了{}分钟,一共专注{}次,感谢对本软件的使用^-^/".format(calculate_total_time(),len(get_focus_records())), self)
        else:
            self.total_time_label = QtWidgets.QLabel("欢迎使用本软件^-^/", self)
        set_pos(self.total_time_label_pos,self.total_time_label)
        self.total_time_label.setStyleSheet(self.label_qss)

        self.text_label = QtWidgets.QLabel("也请不要太重视时长,以自我感受为主，不要消耗自己哦。【该玩玩=-=】", self)
        set_pos(self.text_label_pos,self.text_label)
        self.text_label.setStyleSheet(self.lite_label_qss)

        self.habbit_label = QtWidgets.QLabel(self)
        set_pos(self.habbit_label_pos,self.habbit_label)

        self.week_report_label = QtWidgets.QLabel(self)
        set_pos(self.week_report_pos,self.week_report_label)