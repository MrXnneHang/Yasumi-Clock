import sys
import os

# --- 关键补丁：在所有其他导入之前，处理无控制台模式下的标准输出问题 ---
# 当以无控制台模式（pyinstaller -w 或 console=False）运行时，sys.stdout 和 sys.stderr 可能为 None。
# 某些库（如本例中的 scipy/numpy）在初始化时可能会尝试写入这些流，导致 AttributeError。
# 我们创建一个什么都不做的“哑”流来防止程序崩溃。
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
# --- 补丁结束 ---

import sys
import ctypes
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer, QTime, Qt, QUrl
from PyQt5.QtGui import QPixmap, QImage,QIcon

import numpy as np
import threading
from PIL import Image
from time import sleep


from util import load_config,split_gif_to_frames,combine_path,save_config, SoundPlayer
from yasumi_draw_rec import ManualSelectionWindow
from MainWindowThread import DrawAnimationThread
from LoadingWindow import LoadingWindow
from yasumi_window import yasumiWindow
from MainWindowUI import Main_Window_UI
from SettingsWindow import SettingsWindow



class Main_Window_Response(Main_Window_UI):
    """主窗口的响应

    属性:
    self.timer:更新倒计时，每秒一次。
    self.CloseYausmi:定时五分钟关闭Yausmi Window
    self.total_time:这一次要计时的时长
    self.time_index:加减时长

    函数:
    list_main_button_pos:返回要复刻的Buttons。
    showDrawMainWindow:新建窗口复刻main Window布局,并且打印画矩形的x,y,w,h
    Show:关闭加载窗口，打开主窗口
    change_animation(action):将播放动画指定为action(play/work)
    """
    def __init__(self,loading_window):
        super().__init__()
        
        self.startdrawButton.clicked.connect(self.showDrawMainWindow)
        self.startFanqieButton.clicked.connect(self.startFanqie)
        self.addTimeButton.clicked.connect(self.add_time)
        self.subTimeButton.clicked.connect(self.sub_time)
        self.resetTimeButton.clicked.connect(self.resetTime)
        self.settingsButton.clicked.connect(self.show_settings_window)
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
 
        self.timerRunning = False
        
        # 初始化声音播放器
        self.notification_player = SoundPlayer()
        
        self.start_drawgif_task(action="play")
    
    def show_settings_window(self):
        """显示设置窗口"""
        settings_window = SettingsWindow(self)
        settings_window.exec_()  # 使用 exec_() 以模态方式显示对话框

        # --- 关键修复: 设置窗口关闭后，重新加载配置文件以使更改生效 ---
        self.window_config = load_config(
            self.absolute_dir / "yasumi_config.yml",
            self.absolute_dir / "user_config.yml"
        )
        self.yasumi_clock_config = self.window_config["yasumi_clock"]
        print("配置已重新加载。")
    
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


    def showDrawMainWindow(self):
        child_window_pos = self.list_main_button_pos()
        self.selectionWindow = ManualSelectionWindow(self.main_window_pos,child_window_pos)
        self.selectionWindow.setWindowIcon(QIcon(combine_path(mainWindow.absolute_dir,mainWindow.src_config["icon"])))
        self.selectionWindow.show()
    def startFanqie(self):
        if not self.timerRunning:
            self.change_animation(action="work")
            self.startCountdown(self.total_time[self.time_index])
            self.timerRunning = True
        else:
            print("已经有计时器在运行")
            pass
       

    
    def startCountdown(self,time_str):

        try:
            # 将输入的时间字符串分割成分钟和秒数
            minutes, seconds = map(int, time_str.split(':'))
            # 设置剩余时间
            self.timeRemaining = QTime(0, minutes, seconds)
            # 启动计时器，每秒更新一次
            self.timer.start(1000)
        except ValueError:
            # 如果输入的时间格式无效，则显示错误信息
            self.timeLabel.setText("Invalid time format!")

    def updateTimer(self):
        if self.timeRemaining == QTime(0, 0):
            self.timer.stop()
            self.timeLabel.setText("End!")
            self.timerRunning = False
            self.yasumi = yasumiWindow(self)
            self.yasumi.setWindowIcon(QIcon(combine_path(mainWindow.absolute_dir,mainWindow.src_config["icon"])))
            
            self.yasumi.finished.connect(self.on_yasumi_window_closed)

            self.yasumi.show()
            self.change_animation(action="play")
            self.closeYasumi.singleShot(5*1000,self.yasumi.close)
        else:
            self.timeRemaining = self.timeRemaining.addSecs(-1)
            self.timeLabel.setText(self.timeRemaining.toString("mm:ss"))

    def on_yasumi_window_closed(self):
        """当休息窗口关闭时被调用。"""
        print("休息窗口已关闭，准备播放提醒音。")
        self.play_notification_sound()

    def play_notification_sound(self, notification_config=None, on_finish=None):
        """使用 SoundPlayer 播放提醒音。"""
        try:
            if notification_config is None:
                notification_config = self.yasumi_clock_config.get("notification", {})

            if not notification_config.get("enabled", False):
                print("通知功能已禁用，不播放提醒音。")
                if on_finish:
                    on_finish()
                return

            sound_key = notification_config.get("sound", "default")
            mode = notification_config.get("mode", "play_once")
            loop_count = notification_config.get("loop_count", 3)
            output_device_id = notification_config.get("output_device_id", -1)
            
            sound_rel_path = self.src_config.get("notification_sounds", {}).get(sound_key)
            if not sound_rel_path:
                print(f"错误：在 src.yml 中找不到键 '{sound_key}'。")
                if on_finish:
                    on_finish()
                return

            sound_abs_path = combine_path(self.absolute_dir, sound_rel_path)
            if not os.path.exists(sound_abs_path):
                print(f"错误：找不到音频文件: {sound_abs_path}")
                if on_finish:
                    on_finish()
                return

            volume = notification_config.get("volume", 80)
            device_to_use = output_device_id if output_device_id != -1 else None

            # 转换播放模式为 loop_count
            if mode == "loop_play":
                loop_count_for_player = -1  # -1 代表无限循环
            elif mode == "loop_n_times":
                loop_count_for_player = loop_count
            else: # play_once
                loop_count_for_player = 1

            print(f"播放模式: {mode}, 音量: {volume}, 循环次数: {loop_count_for_player}, 设备ID: {device_to_use}")

            # 使用 SoundPlayer 实例进行播放
            self.notification_player.play(
                sound_path=sound_abs_path,
                volume=volume,
                loop_count=loop_count_for_player,
                device_id=device_to_use,
                on_finish=on_finish
            )

        except Exception as e:
            print(f"播放音频时发生未知错误: {e}")
            if on_finish:
                on_finish()

    def Show(self):
        self.show()
        if self.loadingwindow:
            self.loadingwindow.close()

    def list_main_button_pos(self):
        return [self.draw_button_pos,self.start_fanqie_pos,self.animation_pos,
                self.timer_pos,self.addTime_pos,self.subTime_pos,
                self.resetTime_pos,self.setTime_pos,
                self.settings_button_pos
                ]

    def closeEvent(self, event):
        """重写关闭事件，以处理强制休息模式"""
        # 检查 yasumi 窗口是否存在并且可见
        if hasattr(self, 'yasumi') and self.yasumi and self.yasumi.isVisible():
            if self.yasumi_clock_config.get("force_rest", False):
                print("强制休息模式激活，主窗口将被隐藏而不是关闭。")
                event.ignore()  # 忽略默认的关闭操作
                self.hide()      # 隐藏主窗口
            else:
                # 如果不是强制模式，则正常退出
                print("非强制模式，正常退出。")
                event.accept()
                sys.exit()
        else:
            # 如果休息窗口不存在或不可见，则正常退出
            print("正常退出程序。")
            event.accept()
            sys.exit()
        
    def on_yasumi_closed(self):
        """休息窗口关闭时的回调"""
        print("接收到休息窗口关闭信号，程序即将退出。")
        QtWidgets.QApplication.quit()  # 彻底退出程序


if __name__ == '__main__':
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)

    # --- 新增的全局图标设置逻辑 ---
    # 1. 加载一次图标资源路径。注意此时 mainWindow 还未创建，所以不能用它的属性。
    #    我们直接使用工具函数来获取路径。
    #    这里需要先导入 get_absolute_dir 和 load_config
    from util import get_absolute_dir, load_config, combine_path
    
    absolute_dir = get_absolute_dir()
    src_config = load_config(absolute_dir / "src.yml")
    icon_path = combine_path(absolute_dir, src_config["icon"])
    
    # 2. 创建 QIcon 对象并设置为应用程序的全局图标
    app_icon = QIcon(icon_path)
    app.setWindowIcon(app_icon)
    # --- 全局图标设置结束 ---

    loading_window = LoadingWindow()
    mainWindow = Main_Window_Response(loading_window)
    loading_window.show()

    timer = QtCore.QTimer()
    timer.singleShot(1500, mainWindow.Show)
    
    sys.exit(app.exec_())