import sys
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage,QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from time import sleep
import numpy as np
from util import split_gif_to_frames
from PIL import Image

# 继承自QThread的自定义线程类
class DrawAnimationThread(QThread):
    update_signal = pyqtSignal(np.ndarray)
    def __init__(self):
        super().__init__()
    
    def setup(self,path, label, pos, frame_speed=24,whileTrue=True):
        self.path = path
        self.label = label
        self.pos = pos
        self.frame_speed = frame_speed
        self.whileTrue = whileTrue
    def run(self):
        self.running = True
        frames = split_gif_to_frames(self.path)

        if self.whileTrue:
        # 循环播放
            while self.running:
                for frame in frames:
                    if not self.running:
                        print("线程已经正常退出")
                        return
                    rgb_image = frame.resize((self.pos[2],self.pos[3]),Image.BILINEAR)
                    rgb_image = np.array(rgb_image)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(q_img)
                    self.label.setPixmap(pixmap)
                    sleep(1 / self.frame_speed)
        else:
            for frame in frames:
                rgb_image = frame.resize((self.pos[2],self.pos[3]),Image.BILINEAR)
                rgb_image = np.array(rgb_image)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)
                self.label.setPixmap(pixmap)
                sleep(1 / self.frame_speed)
            while self.running:
                if not self.running:
                    print("线程已经正常退出")
                    return
    def stop(self):
        self.running = False
        self.quit()