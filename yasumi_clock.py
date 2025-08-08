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
from datetime import datetime, timedelta
import ctypes
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import QTimer, QTime, Qt, QUrl, QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup
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
from StopSoundWindow import StopSoundWindow
from mode_enums import OperatingMode
import pomodoro_logger
from pomodoro_state import IdleState, WorkingState, ShortBreakState, LongBreakState, BreakState, PausedState



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
    sound_finished_signal = QtCore.pyqtSignal()

    def __init__(self,loading_window):
        super().__init__()
        
        # 1. 首先调用 initUI() 来构建和样式化所有界面元素
        self.initUI()

        # 2. 然后，再对已经创建好的控件进行操作（连接信号，设置状态等）
        self.sound_finished_signal.connect(self._on_sound_finish)
        
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
        
        # Pomodoro state
        self.pomodoro_config = {}
        self.pomodoro_count = 0
        self.current_state_str = 'IDLE' # 用字符串来记录状态，方便显示
        self.total_time_classic = ["00:00","05:00","10:00",
                                "15:00","20:00","25:00",
                                "30:00","35:00","40:00"]
        self.time_index_classic = 4

        # --- 日志记录会话信息 ---
        self.session_start_time = None
        self.session_planned_duration_minutes = None
        self.session_type = None
        self.session_total_pause_duration = timedelta(0)
        self.pause_start_time = None
        self.session_pause_count = 0

        # --- 初始化模式 ---
        advanced_enabled = self.yasumi_clock_config.get("advanced_mode_enabled", False)
        if advanced_enabled:
            mode_key = self.yasumi_clock_config.get("active_mode_key", OperatingMode.CUSTOM.value)
            self.active_mode = OperatingMode.from_key(mode_key)
        else:
            self.active_mode = OperatingMode.CLASSIC
            
        # --- 初始化状态机 ---
        self.state = IdleState(self)
        self.apply_preset(self.active_mode) # 初始化时加载模式

        self.timerRunning = False
        
        # 初始化声音播放器
        self.notification_player = SoundPlayer()
        
        self.start_drawgif_task(action="play")
        self.stop_sound_window = None
        self.yasumi = None # 初始化 yasumi 属性
    
    def crossfade_text(self, label, new_text):
        """使用交叉淡入淡出效果来改变一个QLabel的文本"""
        self.fade_out = QPropertyAnimation(label, b"windowOpacity")
        self.fade_out.setDuration(250) # 动画时长 ms
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.InQuad)

        self.fade_in = QPropertyAnimation(label, b"windowOpacity")
        self.fade_in.setDuration(250)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutQuad)

        # 当淡出动画结束时，改变文本并开始淡入
        self.fade_out.finished.connect(lambda: (label.setText(new_text), self.fade_in.start()))
        
        # 启动动画
        self.fade_out.start()

    def show_settings_window(self):
        """显示设置窗口"""
        settings_window = SettingsWindow(self)
        if settings_window.exec_() == QDialog.Accepted:
            # 重新加载配置
            self.window_config = load_config(
                self.absolute_dir / "yasumi_config.yml",
                self.absolute_dir / "user_config.yml"
            )
            self.yasumi_clock_config = self.window_config["yasumi_clock"]
            
            # 应用在设置窗口中选择的模式
            new_mode_key = settings_window.staged_settings.get("active_mode_key", OperatingMode.CLASSIC.value)
            self.active_mode = OperatingMode.from_key(new_mode_key)
            
            # active_mode_key 已经在 SettingsWindow 中保存，这里无需重复保存
            
            self.apply_preset(self.active_mode)
            print(f"设置已保存，模式已切换为: {self.active_mode.display_name(self.yasumi_clock_config)}")
    
    def _update_status_display(self):
        state_map = {
            'IDLE': '准备就绪',
            'WORKING': '工作中',
            'SHORT_BREAK': '短休息',
            'LONG_BREAK': '长休息',
            'PAUSED': '已暂停'
        }
        state_text = state_map.get(self.current_state_str, '未知状态')

        # 统一更新窗口标题
        time_str = self.timeRemaining.toString("mm:ss")
        if self.timerRunning or self.current_state_str == 'PAUSED':
             self.setWindowTitle(f"{time_str} - {state_text} | Yasumi Clock")
        elif self.current_state_str == 'IDLE':
             self.setWindowTitle("Yasumi Clock")
        else:
             self.setWindowTitle(f"{state_text} | Yasumi Clock")

        if self.active_mode == OperatingMode.CLASSIC:
            # 经典模式：隐藏信息卡片和进度指示器
            self.info_card.hide()
            self.progressIndicator.hide()
            return
        else:
            # 其他模式：显示信息卡片和进度指示器
            self.info_card.show()
            self.progressIndicator.show()
        
        cycles_before_long_break = self.pomodoro_config.get('cycles_before_long_break', 4)
        cycles_text = f"({self.pomodoro_count}/{cycles_before_long_break})"
        
        # 获取模式信息并更新UI
        mode_info = self._get_detailed_mode_info()
        self.update_mode_display(mode_info, state_text, cycles_text)

        # Update progress indicator (只在非经典模式下更新)
        progress_dots = '● ' * self.pomodoro_count + '○ ' * (cycles_before_long_break - self.pomodoro_count)
        self.progressIndicator.setText(progress_dots.strip())

    def _get_detailed_mode_info(self):
        """获取简洁的模式信息，现代化展示"""
        if self.active_mode == OperatingMode.CLASSIC:
            return "经典模式"
        
        # 获取简洁的模式名称
        mode_names = {
            OperatingMode.CUSTOM: "自定义模式",
            OperatingMode.STUDENT: "学生模式", 
            OperatingMode.PROFESSIONAL: "专注工作",
            OperatingMode.FRAGMENTED_TIME: "碎片时间"
        }
        mode_name = mode_names.get(self.active_mode, "未知模式")
        
        # 获取配置参数
        work_mins = self.pomodoro_config.get('work_mins', 25)
        short_break_mins = self.pomodoro_config.get('short_break_mins', 5)
        long_break_mins = self.pomodoro_config.get('long_break_mins', 15)
        cycles_before_long_break = self.pomodoro_config.get('cycles_before_long_break', 4)
        
        return {
            'mode_name': mode_name,
            'work_mins': work_mins,
            'short_break_mins': short_break_mins,
            'long_break_mins': long_break_mins,
            'cycles_before_long_break': cycles_before_long_break
        }

    def apply_preset(self, mode: OperatingMode):
        self.active_mode = mode
        
        if mode == OperatingMode.CLASSIC:
            self.pomodoro_config = {} # 清空番茄钟配置
            self.timeLabel.setText(self.total_time_classic[self.time_index_classic])
            if hasattr(self, 'info_card'):
                self.info_card.hide()
            if hasattr(self, 'progressIndicator'):
                self.progressIndicator.hide()
            # 显示 +/- 按钮
            self.addTimeButton.show()
            self.subTimeButton.show()
        else: # 所有其他模式
            # 隐藏 +/- 按钮
            self.addTimeButton.hide()
            self.subTimeButton.hide()
            
            if hasattr(self, 'info_card'):
                self.info_card.show()
            if hasattr(self, 'progressIndicator'):
                self.progressIndicator.show()

            if mode == OperatingMode.CUSTOM:
                self.pomodoro_config = self.yasumi_clock_config.get('presets', {}).get('custom', {})
            else: # Preset modes
                preset_config = self.yasumi_clock_config.get('presets', {}).get(mode.value)
                if preset_config:
                    self.pomodoro_config = preset_config
                else:
                    self.pomodoro_config = self.yasumi_clock_config.get('presets', {}).get('custom', {})
            
            work_mins = self.pomodoro_config.get('work_mins', 25)
            self.timeLabel.setText(f"{work_mins:02d}:00")
        
        self.resetTime()

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
        # 这个函数现在只应该在经典模式下被调用，因为按钮在其他模式下是不可见的
        if self.active_mode == OperatingMode.CLASSIC:
            if self.time_index_classic < 8:
                self.time_index_classic += 1
                self.timeLabel.setText(self.total_time_classic[self.time_index_classic])

    def sub_time(self):
        # 这个函数现在只应该在经典模式下被调用
        if self.active_mode == OperatingMode.CLASSIC:
            if self.time_index_classic > 0:
                self.time_index_classic -= 1
                self.timeLabel.setText(self.total_time_classic[self.time_index_classic])

    def resetTime(self):
        self._log_session(status='interrupted') # 记录被中断的会话
        self.timer.stop()
        self.pomodoro_count = 0
        self.session_total_pause_duration = timedelta(0)
        self.session_pause_count = 0
        # 恢复因暂停而改变的样式
        self.timeLabel.setStyleSheet(self.timeLabel.styleSheet().replace(" color: #A9A9A9;", ""))
        self.transition_to_state(IdleState(self))
        self.setWindowTitle("Yasumi Clock") # <--- 重置时恢复标题
        self.nextUpLabel.setText("") # <--- 清空预告
        self.change_animation(action="play")
        
        # 根据模式控制信息卡片和进度指示器显示
        if hasattr(self, 'info_card'):
            if self.active_mode == OperatingMode.CLASSIC:
                self.info_card.hide()
                if hasattr(self, 'progressIndicator'):
                    self.progressIndicator.hide()
            else:
                self.info_card.show()
                if hasattr(self, 'progressIndicator'):
                    self.progressIndicator.show()


    def startFanqie(self):
        # 统一的、基于状态的事件处理
        if isinstance(self.state, PausedState):
            # 如果当前是暂停状态，则恢复
            self.state.exit_state() # exit_state 会处理状态转换
            self.timer.start(1000)
        elif self.timerRunning:
            # 如果计时器正在运行，则暂停
            self.timer.stop()
            self.transition_to_state(PausedState(self, self.state))
        else:
            # 如果计时器未运行（即在IdleState），则开始
            if self.active_mode == OperatingMode.CLASSIC:
                # 经典模式下，我们手动创建一个WorkingState来开始
                # 但这个WorkingState的结束行为需要被特殊处理
                # 为了简单起见，我们在这里创建一个临时的状态
                class ClassicWorkState(WorkingState):
                    def handle_timer_finish(self):
                        self.context.play_notification_sound()
                        self.context.transition_to_state(IdleState(self.context))
                
                self.transition_to_state(ClassicWorkState(self))
            else:
                # 番茄钟模式
                self.transition_to_state(WorkingState(self))

    

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
        if self.timeRemaining > QTime(0, 0):
            self.timeRemaining = self.timeRemaining.addSecs(-1)
            time_str = self.timeRemaining.toString("mm:ss")
            # 只有在非休息状态下才更新主窗口的计时器
            if not isinstance(self.state, BreakState):
                self.timeLabel.setText(time_str)
            # 更新窗口标题
            # 更新窗口标题的操作已移至 _update_status_display
        else:
            self.timer.stop()
            self.timerRunning = False
            self.state.handle_timer_finish()

    def on_yasumi_window_closed(self):
        """当休息窗口被用户手动关闭时调用，中断休息。"""
        self._log_session(status='interrupted') # 记录被中断的休息
        self.timer.stop()
        self.transition_to_state(IdleState(self))
        print("休息被用户手动中断。")
        self.yasumi = None

    @QtCore.pyqtSlot()
    def _on_sound_finish(self):
        """声音播放完成或停止时的回调 (现在是安全的槽函数)。"""
        if self.stop_sound_window:
            self.stop_sound_window.close()
            self.stop_sound_window = None
        print("声音播放结束，清理停止按钮窗口。")

    def transition_to_state(self, new_state):
        """处理状态转换。"""
        print(f"状态转换: {type(self.state).__name__} -> {type(new_state).__name__}")
        self.state = new_state
        self.state.enter_state()

    def play_notification_sound(self, show_stop_button=True):
        """
        使用 SoundPlayer 播放提醒音。

        Args:
            show_stop_button (bool): 是否显示停止播放的按钮窗口。
        """
        try:
            notification_config = self.yasumi_clock_config.get("notification", {})

            if not notification_config.get("enabled", False):
                print("通知功能已禁用，不播放提醒音。")
                self.sound_finished_signal.emit() # 仍然需要发射信号以进行清理
                return

            # 如果已有停止窗口，先关闭
            if self.stop_sound_window:
                self.stop_sound_window.close()

            # 根据参数决定是否创建并显示停止按钮窗口
            if show_stop_button:
                self.stop_sound_window = StopSoundWindow(stop_callback=self.notification_player.stop)
                self.stop_sound_window.show()

            sound_key = notification_config.get("sound", "default")
            mode = notification_config.get("mode", "play_once")
            loop_count = notification_config.get("loop_count", 3)
            output_device_id = notification_config.get("output_device_id", -1)
            
            sound_rel_path = self.src_config.get("notification_sounds", {}).get(sound_key)
            if not sound_rel_path:
                print(f"错误：在 src.yml 中找不到键 '{sound_key}'。")
                self.sound_finished_signal.emit()
                return

            sound_abs_path = combine_path(self.absolute_dir, sound_rel_path)
            if not os.path.exists(sound_abs_path):
                print(f"错误：找不到音频文件: {sound_abs_path}")
                self.sound_finished_signal.emit()
                return

            volume = notification_config.get("volume", 80)
            device_to_use = output_device_id if output_device_id != -1 else None

            if mode == "loop_play":
                loop_count_for_player = -1
            elif mode == "loop_n_times":
                loop_count_for_player = loop_count
            else:
                loop_count_for_player = 1

            print(f"播放模式: {mode}, 音量: {volume}, 循环次数: {loop_count_for_player}, 设备ID: {device_to_use}")

            # 连接信号
            # 先断开旧的连接，防止重复连接
            try:
                self.notification_player.playback_finished.disconnect(self.sound_finished_signal)
            except TypeError:
                pass # 如果从未连接过，会抛出TypeError，可以安全地忽略
            self.notification_player.playback_finished.connect(self.sound_finished_signal)

            self.notification_player.play(
                sound_path=sound_abs_path,
                volume=volume,
                loop_count=loop_count_for_player,
                device_id=device_to_use
            )

        except Exception as e:
            print(f"播放音频时发生未知错误: {e}")
            self.sound_finished_signal.emit()

    def _log_session(self, status: str):
        """记录当前会话到CSV文件。"""
        if not self.session_start_time:
            return # 没有开始时间，说明没有活动的会话

        end_time = datetime.now()
        gross_duration = end_time - self.session_start_time
        net_duration = gross_duration - self.session_total_pause_duration
        
        session_data = {
            'start_time': self.session_start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'session_type': self.session_type,
            'status': status,
            'planned_duration_minutes': self.session_planned_duration_minutes,
            'actual_duration_seconds': int(net_duration.total_seconds()),
            'pause_duration_seconds': int(self.session_total_pause_duration.total_seconds()),
            'pause_count': self.session_pause_count
        }
        
        pomodoro_logger.log_session(session_data)
        
        # 重置会话变量，防止重复记录
        self.session_start_time = None
        self.session_type = None
        self.session_planned_duration_minutes = None
        self.session_total_pause_duration = timedelta(0)
        self.session_pause_count = 0

    def Show(self):
        self.show()
        if self.loadingwindow:
            self.loadingwindow.close()



    def closeEvent(self, event):
        """重写关闭事件，以处理强制休息模式"""
        self._log_session(status='interrupted') # 记录程序关闭时可能中断的会话
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

    # --- 设置 Fluent Design 主题 ---
    # from qfluentwidgets import setTheme, Theme
    # setTheme(Theme.LIGHT)
    # --- 主题设置结束 ---

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