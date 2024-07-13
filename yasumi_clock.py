import sys
from PyQt5 import QtCore, QtGui, QtWidgets
import pyautogui
from PIL import Image
import numpy as np
from util import load_config
from yasumi_draw_rec import ManualSelectionWindow
from qfluentwidgets import PrimaryPushButton

class Main_Window_UI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config("./yasumi_config.yml")
        self.main_window = self.config["yasumi_clock"]["main_window"]
        self.main_window_pos = self.main_window["window_pos"]
        self.draw_button_pos = self.main_window["start_draw"]
        self.start_fanqie_pos = self.main_window["start_fanqie"]
        self.initUI()
    def initUI(self):
        self.setWindowTitle('Main Window')
        self.setGeometry(self.main_window_pos[0],
                         self.main_window_pos[1],
                         self.main_window_pos[2],
                         self.main_window_pos[3],)
        
        self.startdrawButton = PrimaryPushButton('draw_main_window', self)
        self.startdrawButton.setGeometry(self.draw_button_pos[0],
                                         self.draw_button_pos[1],
                                         self.draw_button_pos[2],
                                         self.draw_button_pos[3])
        self.startFanqieButton = PrimaryPushButton('Start', self)
        self.startFanqieButton.setGeometry(self.start_fanqie_pos[0],
                                           self.start_fanqie_pos[1],
                                           self.start_fanqie_pos[2],
                                           self.start_fanqie_pos[3])

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
