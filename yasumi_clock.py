import sys
import os

# --- 关键补丁：在所有其他导入之前，处理无控制台模式下的标准输出问题 ---
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
# --- 补丁结束 ---

from datetime import datetime, timedelta
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon

from util import ConfigManager
from LoadingWindow import LoadingWindow
from yasumi_window import yasumiWindow
from MainWindowUI import Main_Window_UI
from SettingsWindow import SettingsWindow
from FloatingWindow import FloatingWindow
from IdleReminderWindow import IdleReminderWindow
from mode_enums import OperatingMode
from pomodoro_engine import PomodoroEngine
import pomodoro_logger
from sound_service import SoundService
from animation_service import AnimationService

class Main_Window_Response(Main_Window_UI):
    """
    主窗口的响应类。
    现在主要作为视图控制器(View Controller)，将UI事件转发给引擎，
    并响应引擎的信号来更新UI。
    """

    def __init__(self, loading_window):
        super().__init__()
        
        # 1. 初始化配置管理器
        self.config_manager = ConfigManager()
        
        # 2. 首先调用 initUI() 来构建和样式化所有界面元素
        self.initUI()

        # 3. 然后，再对已经创建好的控件进行操作
        self.loadingwindow = loading_window
        
        # --- 初始化核心服务 ---
        self.engine = PomodoroEngine(self.config_manager, self)
        self.sound_service = SoundService(self.config_manager, self)
        self.animation_service = AnimationService(self.config_manager, self.animation_label, self)
        
        # --- 连接UI事件到引擎 ---
        self.startFanqieButton.clicked.connect(self.engine.start_or_pause)
        self.addTimeButton.clicked.connect(lambda: self.engine.adjust_time_classic(1))
        self.subTimeButton.clicked.connect(lambda: self.engine.adjust_time_classic(-1))
        self.resetTimeButton.clicked.connect(self.engine.reset)
        self.settingsButton.clicked.connect(self.show_settings_window)

        # --- 连接引擎和服务信号到UI更新槽 ---
        self.engine.state_changed.connect(self.on_state_changed)
        self.engine.time_updated.connect(self.on_time_updated)
        self.engine.pomodoro_completed.connect(self.on_pomodoro_completed)
        self.engine.break_started.connect(self.show_yasumi_window)
        self.engine.break_finished.connect(self.on_yasumi_window_closed)
        self.engine.play_sound_requested.connect(self.sound_service.play_notification)
        self.engine.animation_change_requested.connect(self.animation_service.change_animation)
        self.engine.last_minute_tick.connect(self.on_last_minute_tick)
        self.engine.idle_reminder_triggered.connect(self._on_idle_reminder_triggered)

        # --- 初始化其他组件 ---
        self.yasumi = None
        self.idle_reminder_window = None
        self.floating_window = None # 延迟初始化
        
        # --- 启动初始动画 ---
        self.animation_service.change_animation("play")
        
        # 初始化UI状态
        self.engine.set_mode(self.engine.active_mode)

    def crossfade_text(self, label, new_text):
        """使用交叉淡入淡出效果来改变一个QLabel的文本"""
        self.fade_out = QPropertyAnimation(label, b"windowOpacity")
        self.fade_out.setDuration(250)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.InQuad)

        self.fade_in = QPropertyAnimation(label, b"windowOpacity")
        self.fade_in.setDuration(250)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutQuad)

        self.fade_out.finished.connect(lambda: (label.setText(new_text), self.fade_in.start()))
        self.fade_out.start()

    def show_settings_window(self):
        """显示设置窗口"""
        settings_window = SettingsWindow(self)
        if settings_window.exec_() == QDialog.Accepted:
            self.engine.reload_config()
            print(f"设置已保存，模式已切换为: {self.engine.active_mode.display_name(self.engine.yasumi_clock_config)}")
            self.engine.set_mode(self.engine.active_mode)

    @QtCore.pyqtSlot(str, str, str)
    def on_state_changed(self, state_name, time_str, next_up_text):
        """响应引擎状态变化的槽函数。"""
        state_map = {
            'IDLE': '准备就绪', 'WORKING': '工作中', 'SHORT_BREAK': '短休息',
            'LONG_BREAK': '长休息', 'PAUSED': '已暂停'
        }
        state_text = state_map.get(state_name, '未知状态')
        
        self.setWindowTitle(f"{time_str} - {state_text} | Yasumi Clock" if state_name not in ['IDLE'] else "Yasumi Clock")
        
        button_text_map = {'IDLE': '开始', 'PAUSED': '继续'}
        self.startFanqieButton.setText(button_text_map.get(state_name, '暂停'))
        
        self.crossfade_text(self.timeLabel, time_str)
        self.nextUpLabel.setText(next_up_text)
        
        if self.engine.active_mode == OperatingMode.CLASSIC:
            self.info_card.hide()
            self.progressIndicator.hide()
            self.addTimeButton.show()
            self.subTimeButton.show()
        else:
            self.info_card.show()
            self.progressIndicator.show()
            self.addTimeButton.hide()
            self.subTimeButton.hide()
            mode_info = self._get_detailed_mode_info()
            cycles_before_long_break = self.engine.pomodoro_config.get('cycles_before_long_break', 4)
            cycles_text = f"({self.engine.pomodoro_count}/{cycles_before_long_break})"
            self.update_mode_display(mode_info, state_text, cycles_text)

    @QtCore.pyqtSlot(str)
    def on_time_updated(self, time_str):
        """响应引擎时间更新的槽函数。"""
        self.timeLabel.setText(time_str)
        self.setWindowTitle(f"{time_str} - {self.windowTitle().split(' - ')[-1]}")

    @QtCore.pyqtSlot(int)
    def on_pomodoro_completed(self, count):
        """响应番茄钟周期完成的槽函数。"""
        if self.engine.active_mode != OperatingMode.CLASSIC:
            cycles_before_long_break = self.engine.pomodoro_config.get('cycles_before_long_break', 4)
            progress_dots = '● ' * count + '○ ' * (cycles_before_long_break - count)
            self.progressIndicator.setText(progress_dots.strip())

    def _get_detailed_mode_info(self):
        """获取简洁的模式信息，现代化展示"""
        if self.engine.active_mode == OperatingMode.CLASSIC:
            return "经典模式"
        
        mode_names = {
            OperatingMode.CUSTOM: "自定义模式", OperatingMode.STUDENT: "学生模式", 
            OperatingMode.PROFESSIONAL: "专注工作", OperatingMode.FRAGMENTED_TIME: "碎片时间"
        }
        mode_name = mode_names.get(self.engine.active_mode, "未知模式")
        
        config = self.engine.pomodoro_config
        return {
            'mode_name': mode_name,
            'work_mins': config.get('work_mins', 25),
            'short_break_mins': config.get('short_break_mins', 5),
            'long_break_mins': config.get('long_break_mins', 15),
            'cycles_before_long_break': config.get('cycles_before_long_break', 4)
        }

    def _on_idle_reminder_triggered(self):
        """响应空闲提醒信号的槽函数。"""
        idle_config = self.engine.yasumi_clock_config.get("idle_reminder", {})
        
        if idle_config.get("visual_alert", False):
            self.show_idle_reminder_window()

        if idle_config.get("sound_alert", False):
            self.sound_service.play_idle_reminder_sound()

    def show_idle_reminder_window(self):
        """创建并显示空闲提醒窗口，处理窗口的生命周期。"""
        # 如果窗口实例还存在并且可见，先关闭它
        if self.idle_reminder_window and self.idle_reminder_window.isVisible():
            self.idle_reminder_window.close()
        
        # 创建新实例
        self.idle_reminder_window = IdleReminderWindow(self)
        # 连接 destroyed 信号，以便在窗口关闭后清理引用
        self.idle_reminder_window.destroyed.connect(self._on_idle_window_destroyed)
        self.idle_reminder_window.show()

    def _on_idle_window_destroyed(self):
        """当提醒窗口被销毁时，将引用设置为None。"""
        self.idle_reminder_window = None
        print("Idle reminder window destroyed and reference cleaned up.")

    @QtCore.pyqtSlot(str, bool)
    def on_last_minute_tick(self, time_str, show_window):
        """响应最后一分钟的信号，控制悬浮窗的显示和更新。"""
        if show_window:
            if not self.floating_window or not self.floating_window.isVisible():
                # 如果窗口不存在或不可见，则（重新）创建它
                if self.floating_window:
                    self.floating_window.close() # 关闭旧实例
                
                floating_window_config = self.engine.yasumi_clock_config.get("floating_window", {})
                position = floating_window_config.get("position", "top_right")
                size_scale = floating_window_config.get("size_scale", 1.0)
                
                self.floating_window = FloatingWindow(position=position, size_scale=size_scale)
                self.floating_window.show()

            self.floating_window.update_time(time_str)
        else:
            if self.floating_window and self.floating_window.isVisible():
                self.floating_window.hide()
 
    def show_yasumi_window(self):
        """显示休息窗口。"""
        if self.yasumi:
            self.yasumi.close()
        
        self.yasumi = yasumiWindow(self)
        icon_path = self.config_manager.get_resource_path(self.src_config["icon"])
        self.yasumi.setWindowIcon(QIcon(icon_path))
        self.yasumi.finished.connect(self.engine.on_break_window_closed)
        self.yasumi.show()

    def on_yasumi_window_closed(self):
        """当休息窗口被关闭时调用（无论是完成还是中断）。"""
        if self.yasumi and self.yasumi.isVisible():
            try:
                self.yasumi.finished.disconnect(self.engine.on_break_window_closed)
            except TypeError:
                pass
            self.yasumi.close()
        self.yasumi = None

    def Show(self):
        start_minimized = self.config_manager.get_config().get('yasumi_clock', {}).get('start_minimized', False)
        if start_minimized:
            self.showMinimized()
        else:
            self.show()
        
        if self.loadingwindow:
            self.loadingwindow.close()

    def closeEvent(self, event):
        """重写关闭事件，以处理强制休息模式"""
        self.animation_service.stop_all()
        self.engine._log_session(status='interrupted')
        if self.yasumi and self.yasumi.isVisible():
            if self.engine.yasumi_clock_config.get("force_rest", False):
                print("强制休息模式激活，主窗口将被隐藏而不是关闭。")
                event.ignore()
                self.hide()
            else:
                event.accept()
                sys.exit()
        else:
            event.accept()
            sys.exit()
        
    def on_yasumi_closed(self):
        """休息窗口关闭时的回调"""
        print("接收到休息窗口关闭信号，程序即将退出。")
        QtWidgets.QApplication.quit()

if __name__ == '__main__':
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)

    from util import ConfigManager
    
    config_manager = ConfigManager()
    src_config = config_manager.get_src_config()
    icon_path = config_manager.get_resource_path(src_config["icon"])
    
    app_icon = QIcon(icon_path)
    app.setWindowIcon(app_icon)

    loading_window = LoadingWindow()
    mainWindow = Main_Window_Response(loading_window)
    loading_window.show()

    timer = QtCore.QTimer()
    timer.singleShot(1500, mainWindow.Show)
    
    sys.exit(app.exec_())