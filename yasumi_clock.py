import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QPixmap, QImage,QIcon
import pyautogui
from PIL import Image
import numpy as np
from util import load_config
from yasumi_draw_rec import ManualSelectionWindow
from qfluentwidgets import PrimaryPushButton
import PIL
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

        # Image Source
        self.example_img_path = self.src_config["example"]

        # Init
        self.initUI()
    def initUI(self):
        self.setWindowTitle('Main Window')
        self.setGeometry(self.main_window_pos[0],
                         self.main_window_pos[1],
                         self.main_window_pos[2],
                         self.main_window_pos[3],)
        
        # Buttons
        self.startdrawButton = PrimaryPushButton('Draw Main Window', self)
        self.startdrawButton.setGeometry(self.draw_button_pos[0],
                                         self.draw_button_pos[1],
                                         self.draw_button_pos[2],
                                         self.draw_button_pos[3])
        self.startFanqieButton = PrimaryPushButton('Start', self)
        self.startFanqieButton.setGeometry(self.start_fanqie_pos[0],
                                           self.start_fanqie_pos[1],
                                           self.start_fanqie_pos[2],
                                           self.start_fanqie_pos[3])
        
        # Labels
        self.Animation_Label = QtWidgets.QLabel(self)
        self.Animation_Label.setGeometry(QtCore.QRect(self.animation_pos[0],
                                                      self.animation_pos[1],
                                                      self.animation_pos[2],
                                                      self.animation_pos[3]))
        self.Animation_Label.setText("")
        self.Animation_Label.setObjectName("Animation")

        # Func
        self.Draw_Image(Label=self.Animation_Label,
                        path=self.example_img_path,
                        Pos=self.animation_pos)
    def Draw_Image(self,Label,path,Pos):
        img = PIL.Image.open(path)
        img = img.resize((Pos[2],Pos[3]),Image.BILINEAR)
        img = np.array(img)
        rgb_image = img
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        Label.setPixmap(pixmap)


class Main_Window_Response(Main_Window_UI):
    def __init__(self):
        super().__init__()
        self.startdrawButton.clicked.connect(self.showDrawMainWindow)

    def showDrawMainWindow(self):
        child_window_pos = self.list_main_button_pos()
        self.selectionWindow = ManualSelectionWindow(self.main_window_pos,child_window_pos)
        self.selectionWindow.show()
    def list_main_button_pos(self):
        return [self.draw_button_pos,self.start_fanqie_pos]



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    mainWindow = Main_Window_Response()
    mainWindow.show()
    sys.exit(app.exec_())
