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

import util
import logging
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

class Main_Window_Response(QtWidgets.QWidget):
    """
    主窗口的响应类。
    现在主要作为视图控制器(View Controller)，将UI事件转发给引擎，
    并响应引擎的信号来更新UI。
    """

    def __init__(self, loading_window, is_autostart=False):
        super().__init__()
        self.config_manager = util.ConfigManager()
        self.src_config = self.config_manager.get_src_config()
        self.engine = PomodoroEngine(self.config_manager, self)
        self.sound_service = SoundService(self.config_manager, self)
        
        self.loadingwindow = loading_window
        self.is_autostart = is_autostart # 保存启动方式

        # 设置布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # 创建初始UI
        self.current_ui = Main_Window_UI()
        self.current_ui.initUI()
        self.layout().addWidget(self.current_ui)
        
        # 创建动画服务
        self.animation_service = AnimationService(self.config_manager, self.current_ui.animation_label, self)

        # 白噪音播放器
        self.white_noise_player = None
        self.white_noise_enabled = False
    
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
        self.engine.state_changed.connect(self._handle_white_noise)

        # --- 初始化其他组件 ---
        self.yasumi = None
        self.idle_reminder_window = None
        self.floating_window = None
        
        # 连接UI事件
        self.current_ui.startFanqieButton.clicked.connect(self.engine.start_or_pause)
        if hasattr(self.current_ui, 'addTimeButton'):
            self.current_ui.addTimeButton.clicked.connect(lambda: self.engine.adjust_time_classic(1))
            self.current_ui.subTimeButton.clicked.connect(lambda: self.engine.adjust_time_classic(-1))
        self.current_ui.resetTimeButton.clicked.connect(self.engine.reset)
        self.current_ui.settingsButton.clicked.connect(self.show_settings_window)
        
        # --- 启动初始动画 ---
        self.animation_service.change_animation("play")
        
        # 初始化UI状态
        self.engine.set_mode(self.engine.active_mode)

        
    def setup_ui_for_mode(self, mode):
        # 停止所有动画线程
        if hasattr(self, 'animation_service'):
            self.animation_service.stop_all()
        
        if self.current_ui:
            # 从布局中移除旧的UI
            old_layout = self.layout()
            if old_layout:
                old_layout.removeWidget(self.current_ui)
            
            self.current_ui.setParent(None)
            self.current_ui.deleteLater()

        self.current_ui = Main_Window_UI()
        self.current_ui.initUI()
        
        # 确保有布局
        if not self.layout():
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            self.setLayout(layout)
        
        # 添加新的UI到布局
        self.layout().addWidget(self.current_ui)
        
        # 更新animation_service的animation_label引用
        if hasattr(self, 'animation_service'):
            self.animation_service.animation_label = self.current_ui.animation_label

        # 连接UI事件到引擎
        self.current_ui.startFanqieButton.clicked.connect(self.engine.start_or_pause)
        if hasattr(self.current_ui, 'addTimeButton'):
            self.current_ui.addTimeButton.clicked.connect(lambda: self.engine.adjust_time_classic(1))
            self.current_ui.subTimeButton.clicked.connect(lambda: self.engine.adjust_time_classic(-1))
        self.current_ui.resetTimeButton.clicked.connect(self.engine.reset)
        self.current_ui.settingsButton.clicked.connect(self.show_settings_window)

        # 根据当前状态重新启动动画
        if hasattr(self, 'animation_service'):
            if self.engine.state.name == 'WORKING':
                self.animation_service.change_animation("work")
            else:
                self.animation_service.change_animation("play")

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
            if settings_window.timing_settings_changed:
                logging.info("Timing-related settings changed. Reloading config and resetting pomodoro state.")
                # 重新加载配置并重置状态
                self.engine.reload_config_and_reset()
                logging.info(f"设置已保存，模式已切换为: {self.engine.active_mode.display_name(self.engine.yasumi_clock_config)}")
            else:
                logging.info("Settings saved without timing changes. Reloading config without resetting state.")
                # 只重新加载配置，不重置状态
                self.engine.reload_config_without_reset()

            # 确保在UI更新后同步高度
            # 使用QTimer确保同步操作在所有其他UI事件处理完毕后执行
            QtCore.QTimer.singleShot(0, self.current_ui.sync_panel_heights)

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
        self.current_ui.startFanqieButton.setText(button_text_map.get(state_name, '暂停'))
        
        self.crossfade_text(self.current_ui.timeLabel, time_str)
        self.current_ui.nextUpLabel.setText(next_up_text)
        
        if self.engine.active_mode == OperatingMode.CLASSIC:
            self.current_ui.info_card.hide()
            self.current_ui.progressIndicator.hide()
            self.current_ui.addTimeButton.show()
            self.current_ui.subTimeButton.show()
        else:
            self.current_ui.info_card.show()
            self.current_ui.progressIndicator.show()
            if hasattr(self.current_ui, 'addTimeButton'):
                self.current_ui.addTimeButton.hide()
                self.current_ui.subTimeButton.hide()
            mode_info = self._get_detailed_mode_info()
            
            cycles_before_long_break = self.engine.pomodoro_config.get('cycles_before_long_break', 4)
            cycles_text = f"({self.engine.pomodoro_count}/{cycles_before_long_break})"
            
            self.current_ui.update_mode_display(mode_info, state_text, cycles_text)

    @QtCore.pyqtSlot(str)
    def on_time_updated(self, time_str):
        """响应引擎时间更新的槽函数。"""
        self.current_ui.timeLabel.setText(time_str)
        self.setWindowTitle(f"{time_str} - {self.windowTitle().split(' - ')[-1]}")

    @QtCore.pyqtSlot(int)
    def on_pomodoro_completed(self, count):
        """响应番茄钟周期完成的槽函数。"""
        if self.engine.active_mode != OperatingMode.CLASSIC:
            cycles_before_long_break = self.engine.pomodoro_config.get('cycles_before_long_break', 4)
            progress_dots = '● ' * count + '○ ' * (cycles_before_long_break - count)
            self.current_ui.progressIndicator.setText(progress_dots.strip())

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
        """创建并显示空闲提醒窗口，确保只有一个实例存在。"""
        # 如果窗口实例已存在，则激活它并返回，不再创建新的
        if self.idle_reminder_window:
            self.idle_reminder_window.activateWindow()
            self.idle_reminder_window.raise_()
            return

        # 创建新实例
        self.idle_reminder_window = IdleReminderWindow(self)
        # 连接 destroyed 信号，以便在窗口关闭后清理引用
        self.idle_reminder_window.destroyed.connect(self._on_idle_window_destroyed)
        self.idle_reminder_window.show()

    def _handle_white_noise(self, state_name, time_str, next_up_text):
        """根据状态控制白噪音播放"""
        # 获取白噪音设置
        white_noise_config = self.engine.yasumi_clock_config.get("white_noise", {})
        self.white_noise_enabled = white_noise_config.get("enabled", False)
        
        if not self.white_noise_enabled:
            self._stop_white_noise()
            return
        
        # 仅在专注工作时播放白噪音
        if state_name == 'WORKING':
            self._start_white_noise()
        else:
            self._stop_white_noise()

    def _stop_white_noise(self):
        """停止播放白噪音"""
        if self.white_noise_player and self.white_noise_player.is_playing():
            self.white_noise_player.stop()
            self.white_noise_player = None
            logging.info("白噪音停止播放")
    
    def _start_white_noise(self):
        """开始播放白噪音"""
        if self.white_noise_player and self.white_noise_player.is_playing():
            return
            
        try:
            # 获取白噪音音频文件路径
            white_noise_path = self.config_manager.get_resource_path("src/audio/rain.mp3")
            if not os.path.exists(white_noise_path):
                logging.warning("白噪音音频文件不存在")
                return
                
            # 使用SoundPlayer播放白噪音（循环播放）
            self.white_noise_player = util.SoundPlayer()
            self.white_noise_player.play(
                sound_path=str(white_noise_path),
                volume=50,  # 默认音量50%
                loop_count=-1,  # 无限循环
                device_id=None  # 使用默认设备
            )
            logging.info("白噪音开始播放")
            
        except Exception as e:
            logging.error(f"播放白噪音失败: {e}")

    def _on_idle_window_destroyed(self):
        """当提醒窗口被销毁时，将引用设置为None。"""
        self.idle_reminder_window = None
        logging.info("Idle reminder window destroyed and reference cleaned up.")

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
        config = self.config_manager.get_config().get('yasumi_clock', {})
        
        minimize = False
        if self.is_autostart:
            # 如果是自启动，检查自启动最小化设置
            minimize = config.get('minimize_on_auto_start', True)
        else:
            # 如果是手动启动，检查手动启动最小化设置
            minimize = config.get('minimize_on_manual_start', False)

        if minimize:
            self.showMinimized()
        else:
            self.show()
        
        if self.loadingwindow:
            self.loadingwindow.close()

    def closeEvent(self, event):
        """重写关闭事件，以保存会话状态并处理强制休息模式"""
        # 1. 根据设置保存或清除会话状态
        should_resume = self.engine.yasumi_clock_config.get("resume_unfinished_session", True)
        if should_resume:
            current_state = self.engine.get_session_state()
            self.config_manager.save_session_state(current_state)
            if current_state:
                logging.info(f"Session state saved on exit: {current_state}")
            else:
                logging.info("Exiting from an idle state. No session state saved.")
        else:
            # 如果禁用了恢复功能，则清除任何可能存在的状态
            self.config_manager.save_session_state(None)
            logging.info("Resume session is disabled. Clearing any saved session state.")

        # 2. 停止动画和日志记录和白噪音
        self.animation_service.stop_all()
        self.engine._log_session(status='interrupted')
        self._stop_white_noise()

        # 3. 处理强制休息模式
        if self.yasumi and self.yasumi.isVisible():
            if self.engine.yasumi_clock_config.get("force_rest", False):
                logging.info("强制休息模式激活，主窗口将被隐藏而不是关闭。")
                event.ignore()
                self.hide()
            else:
                # 允许关闭
                event.accept()
                # 使用 QApplication.quit() 来确保干净的退出流程
                QtWidgets.QApplication.quit()
        else:
            # 正常关闭
            event.accept()
            QtWidgets.QApplication.quit()
        
    def on_yasumi_closed(self):
        """休息窗口关闭时的回调"""
        logging.info("接收到休息窗口关闭信号，程序即将退出。")
        QtWidgets.QApplication.quit()

if __name__ == '__main__':
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)

    # --- 初始化日志 ---
    util.setup_logger()
    
    config_manager = util.ConfigManager()
    src_config = config_manager.get_src_config()
    icon_path = config_manager.get_resource_path(src_config["icon"])
    
    app_icon = QIcon(icon_path)
    app.setWindowIcon(app_icon)

    loading_window = LoadingWindow()
    # 检查是否包含 --autostart 参数
    is_autostart = "--autostart" in sys.argv
    logging.info(f"Application started. Is autostart: {is_autostart}")
    
    mainWindow = Main_Window_Response(loading_window, is_autostart=is_autostart)
    loading_window.show()

    timer = QtCore.QTimer()
    timer.singleShot(1500, mainWindow.Show)
    
    sys.exit(app.exec_())