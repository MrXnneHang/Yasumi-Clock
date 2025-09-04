import sys
import cv2
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
        
        # 将大延迟拆分为小间隔，以便更频繁检查停止标志
        delay_ms = int(1000 / self.frame_speed)
        for _ in range(delay_ms):
            if not self.running:
                return False
            self.msleep(1)
        return True

    def run(self):
        self.running = True
        cap = None
        try:
            cap = cv2.VideoCapture(self.path)
            if not cap.isOpened():
                logging.error(f"无法打开视频文件: {self.path}")
                return

            # 设置读取超时，避免卡在损坏的视频文件上
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_count <= 0:
                logging.warning(f"视频文件可能损坏: {self.path}")
                return

            while self.running:
                # 在每次读取前检查停止标志
                if not self.running:
                    break
                    
                ret, frame = cap.read()
                if not ret:
                    if self.whileTrue:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        break
                
                # Convert BGR (from cv2) to RGB (for QImage)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                if not self._process_and_display_frame(rgb_frame):
                    break  # Stop signal received during frame processing

        except Exception as e:
            logging.error(f"动画线程发生错误: {str(e)}")
        finally:
            if cap:
                cap.release()
            logging.info("动画线程已退出。")
    def stop(self):
        """停止线程运行"""
        self.running = False
        # 立即退出事件循环
        self.quit()
        # 如果线程正在sleep，这会中断它
        self.requestInterruption()