import sys
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QPixmap, QImage,QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from time import sleep
import numpy as np
from util import split_gif_to_frames,split_mp4_to_frames
from PIL import Image


import numpy as np

def process_image(rgb_image):
    if len(rgb_image.shape) == 2:  # 如果图像是单通道
        h, w = rgb_image.shape
        # 将单通道的图像转换为三通道的灰度图像
        rgb_image = np.stack((rgb_image, rgb_image, rgb_image), axis=-1)
        h, w, ch = rgb_image.shape
    elif len(rgb_image.shape) == 3:  # 如果图像是三通道的
         h, w, ch = rgb_image.shape
    else: #  其他情况
        raise ValueError(f"unsupported image shape: {rgb_image.shape}")
    
    # 在这里执行你的后续操作，例如使用 h, w, ch
    return h, w, ch , rgb_image

# 继承自QThread的自定义线程类
class DrawAnimationThread(QThread):
    """绘制mp4或者gif到QLabel

    属性:
    self.frame_speed: 帧率
    self.whileTrue: True循环播放，False只播放一遍
    self.Running: True:持续运行，False:停止运行

    用法:
    self.yasumi_thread = None
    self.start_draw_thread()
    def start_draw_thread():
        if not self.yasumi_thread or not self.yasumi_thread.isRunning():
            self.yasumi_thread = DrawAnimationThread()
            self.yasumi_thread.setup(path=self.gif,
                                        label=self.animation_label,
                                        pos=(0,
                                             0,
                                            self.screen_width // 6 * 5,
                                            self.screen_height // 6 * 5),
                                        frame_speed=24,
                                        whileTrue=False)
            self.yasumi_thread.start()
    """
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
        if self.path.split(".")[-1] == "gif":
            frames = split_gif_to_frames(self.path)
        elif self.path.split(".")[-1] == "mp4":
            frames = split_mp4_to_frames(self.path)
        else:
            print("未知格式的视频,目前支持mp4,gif。")

        if self.whileTrue:
        # 循环播放
            while self.running:
                for frame in frames:
                    if not self.running:
                        print("线程已经正常退出")
                        return
                    rgb_image = np.array(frame)
                    h, w, ch, rgb_image = process_image(rgb_image)
                    bytes_per_line = ch * w
                    q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(q_img)
                    pixmap = pixmap.scaled(self.pos[2], self.pos[3], Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.label.setPixmap(pixmap)
                    sleep(1 / self.frame_speed)
        else:
            for frame in frames:
                rgb_image = np.array(frame)
                h, w, ch, rgb_image = process_image(rgb_image)
                bytes_per_line = ch * w
                q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)
                pixmap = pixmap.scaled(self.pos[2], self.pos[3], Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.label.setPixmap(pixmap)
                sleep(1 / self.frame_speed)
            while self.running:
                if not self.running:
                    print("线程已经正常退出")
                    return
    def stop(self):
        self.running = False
        self.quit()