import sys
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QPixmap, QImage,QIcon
from qfluentwidgets import PrimaryPushButton

import numpy as np
import threading
from PIL import Image
from time import sleep



from util import load_config,split_gif_to_frames
from yasumi_draw_rec import ManualSelectionWindow
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

        # Label for animation
        self.animation_label = QtWidgets.QLabel(self)
        self.animation_label.setGeometry(QtCore.QRect(self.animation_pos[0],
                                                      self.animation_pos[1],
                                                      self.animation_pos[2],
                                                      self.animation_pos[3]))

        # Start thread to draw GIF frames

        # self.Draw_Image(Label=self.animation_label,
        #                 path=self.example_img_path,
        #                 Pos=self.animation_pos)

        self.start_drawgif_task()

 
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
    mainWindow.setWindowIcon(QIcon(mainWindow.src_config["icon"]))
    mainWindow.show()
    sys.exit(app.exec_())
