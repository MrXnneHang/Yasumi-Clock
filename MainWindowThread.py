import sys
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QPixmap, QImage,QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from time import sleep
import numpy as np
from util import split_gif_to_frames,split_mp4_to_frames
from PIL import Image
import logging


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
    def _process_and_display_frame(self, frame):
        """处理单帧图像并将其显示在QLabel上。"""
        if not self.running:
            return False
        
        rgb_image = np.array(frame)
        h, w, ch, rgb_image = process_image(rgb_image)
        bytes_per_line = ch * w
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        pixmap = pixmap.scaled(self.pos[2], self.pos[3], Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(pixmap)
        sleep(1 / self.frame_speed)
        return True

    def run(self):
        self.running = True
        file_extension = self.path.split(".")[-1]
        
        if file_extension == "gif":
            frames = split_gif_to_frames(self.path)
        elif file_extension == "mp4":
            frames = split_mp4_to_frames(self.path)
        else:
            logging.error(f"未知格式的文件: {self.path}")
            return

        if not frames:
            logging.error(f"无法从 {self.path} 加载帧。")
            return

        while self.running:
            for frame in frames:
                if not self._process_and_display_frame(frame):
                    logging.info("线程已停止。")
                    return
            
            if not self.whileTrue:
                break # 如果不循环，则在播放完所有帧后退出
        
        logging.info("线程已正常退出。")
    def stop(self):
        self.running = False
        self.quit()