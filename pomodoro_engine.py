from PyQt5.QtCore import QObject, QTimer, pyqtSignal, QTime
from datetime import datetime, timedelta
from mode_enums import OperatingMode
from pomodoro_state import IdleState, WorkingState, ShortBreakState, LongBreakState, ClassicBreakState, PausedState, PomodoroState
import pomodoro_logger

class PomodoroEngine(QObject):
    """
    封装番茄钟核心逻辑，包括状态管理、计时器和模式切换。
    通过信号与UI层通信。
    """
    # --- Signals ---
    state_changed = pyqtSignal(str, str, str) # state_name, time_str, next_up_text
    time_updated = pyqtSignal(str) # time_str
    last_minute_tick = pyqtSignal(str, bool) # time_str, show_window
    pomodoro_completed = pyqtSignal(int) # pomodoro_count
    break_started = pyqtSignal()
    break_finished = pyqtSignal()
    play_sound_requested = pyqtSignal()
    animation_change_requested = pyqtSignal(str) # "work" or "play"

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.yasumi_clock_config = self.config_manager.get_config().get("yasumi_clock", {})
        self.is_debug = self.yasumi_clock_config.get('debug', False)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_timer)
        
        self.time_remaining = QTime(0, 0)
        self.pomodoro_count = 0
        
        self.active_mode = OperatingMode.CLASSIC
        self.pomodoro_config = {}
        
        # --- Classic Mode Specific ---
        self.total_time_classic = ["00:00", "05:00", "10:00", "15:00", "20:00", "25:00", "30:00", "35:00", "40:00"]
        self.time_index_classic = 4
        
        # --- Logging ---
        self.session_start_time = None
        self.session_planned_duration_minutes = None
        self.session_type = None
        self.session_total_pause_duration = timedelta(0)
        self.pause_start_time = None
        self.session_pause_count = 0
        
        # --- State Machine ---
        self.state = IdleState(self)
        self.reload_config()

    def reload_config(self):
        """从ConfigManager重新加载配置并应用。"""
        config = self.config_manager.get_config()
        self.yasumi_clock_config = config.get("yasumi_clock", {})
        self.is_debug = self.yasumi_clock_config.get('debug', False)
        
        advanced_enabled = self.yasumi_clock_config.get("advanced_mode_enabled", False)
        if advanced_enabled:
            mode_key = self.yasumi_clock_config.get("active_mode_key", OperatingMode.CUSTOM.value)
            self.set_mode(OperatingMode.from_key(mode_key))
        else:
            self.set_mode(OperatingMode.CLASSIC)

    def set_mode(self, mode: OperatingMode):
        """设置当前的操作模式。"""
        self.active_mode = mode
        if self.state.name != 'IDLE':
            self.reset()

        if mode == OperatingMode.CLASSIC:
            self.pomodoro_config = {}
            if self.is_debug:
                print("--- DEBUG MODE ON: Classic mode timer will be 5 seconds upon starting. ---")
            time_str = self.total_time_classic[self.time_index_classic]
            self.time_remaining, _ = self._parse_time(time_str)
            self.state_changed.emit(self.state.name, time_str, "调整时长后点击开始")
        else:
            preset_key = mode.value if mode != OperatingMode.CUSTOM else 'custom'
            self.pomodoro_config = self.yasumi_clock_config.get('presets', {}).get(preset_key, {})
            
            if self.is_debug:
                print("--- DEBUG MODE ON: Timers will be set to 5 seconds upon starting. ---")

            work_mins = self.pomodoro_config.get('work_mins', 25)
            time_str = f"{int(work_mins):02d}:{int((work_mins*60)%60):02d}"
            self.time_remaining, _ = self._parse_time(time_str)
            self.state_changed.emit(self.state.name, "Begin!", "准备开始专注工作")
        
        self.pomodoro_count = 0
        self.pomodoro_completed.emit(self.pomodoro_count)

    def start_or_pause(self):
        """根据当前状态决定是开始、暂停还是恢复。"""
        if isinstance(self.state, PausedState):
            # 恢复
            self.state.exit_state()
            self.timer.start(1000)
        elif self.timer.isActive():
            # 暂停
            self.timer.stop()
            self.transition_to_state(PausedState(self, self.state))
        else:
            # 开始 - 所有模式都使用统一的WorkingState
            self.transition_to_state(WorkingState(self))

    def reset(self):
        """重置计时器和状态。"""
        self._log_session(status='interrupted')
        self.timer.stop()
        self.last_minute_tick.emit("", False) # 重置时隐藏悬浮窗
        self.pomodoro_count = 0
        self.session_total_pause_duration = timedelta(0)
        self.session_pause_count = 0
        self.transition_to_state(IdleState(self))
        self.pomodoro_completed.emit(self.pomodoro_count)

    def adjust_time_classic(self, delta: int):
        """调整经典模式下的时间。"""
        if self.active_mode != OperatingMode.CLASSIC or self.timer.isActive():
            return
        
        if self.is_debug:
            # Debug模式下固定为5秒，不允许调整
            return
            
        new_index = self.time_index_classic + delta
        if 0 <= new_index < len(self.total_time_classic):
            self.time_index_classic = new_index
            time_str = self.total_time_classic[self.time_index_classic]
            self.time_remaining, _ = self._parse_time(time_str)
            self.time_updated.emit(time_str)

    def transition_to_state(self, new_state: PomodoroState):
        """处理状态转换。"""
        print(f"Engine state transition: {type(self.state).__name__} -> {type(new_state).__name__}")
        self.state = new_state
        self.state.enter_state()

    def start_countdown(self, time_str: str):
        """根据给定的时间字符串开始倒计时。"""
        try:
            self.time_remaining, total_seconds = self._parse_time(time_str)
            self.timer.start(1000)
        except ValueError:
            print(f"Invalid time format for countdown: {time_str}")

    def _update_timer(self):
        """每秒更新计时器。"""
        if self.time_remaining > QTime(0, 0):
            self.time_remaining = self.time_remaining.addSecs(-1)
            time_str = self.time_remaining.toString("mm:ss")
            if not isinstance(self.state, (ShortBreakState, LongBreakState, ClassicBreakState)):
                 self.time_updated.emit(time_str)

            # 检查是否需要显示/更新悬浮窗
            total_seconds = self.time_remaining.minute() * 60 + self.time_remaining.second()
            show_last_minute_window = self.yasumi_clock_config.get("show_last_minute_window", False)
            
            if show_last_minute_window and total_seconds <= 60 and isinstance(self.state, (WorkingState, PausedState)):
                self.last_minute_tick.emit(time_str, True)
            else:
                # 如果不满足条件，确保窗口是隐藏的
                self.last_minute_tick.emit(time_str, False)

        else:
            self.timer.stop()
            self.last_minute_tick.emit("00:00", False) # 确保在计时结束时隐藏窗口
            self.state.handle_timer_finish()

    def _parse_time(self, time_str: str):
        """将 'mm:ss' 格式的字符串解析为 QTime 对象和总秒数。"""
        parts = list(map(int, time_str.split(':')))
        minutes, seconds = parts[0], parts[1]
        total_seconds = minutes * 60 + seconds
        return QTime(0, minutes, seconds), total_seconds

    def _log_session(self, status: str):
        """记录当前会话到CSV文件。"""
        if not self.session_start_time:
            return

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
        
        # 重置会话变量
        self.session_start_time = None
        self.session_type = None
        self.session_planned_duration_minutes = None
        self.session_total_pause_duration = timedelta(0)
        self.session_pause_count = 0

    def on_break_window_closed(self):
        """当休息窗口被用户手动关闭时调用。"""
        self._log_session(status='interrupted')
        self.timer.stop()
        self.transition_to_state(IdleState(self))
        print("Break interrupted by user.")
