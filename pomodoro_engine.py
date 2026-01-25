from PyQt5.QtCore import QObject, QTimer, pyqtSignal, QTime
from datetime import datetime, timedelta
from mode_enums import OperatingMode
from pomodoro_state import IdleState, WorkingState, ShortBreakState, LongBreakState, ClassicBreakState, PausedState, PomodoroState
import pomodoro_logger
import logging
import platform

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
    idle_reminder_triggered = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.yasumi_clock_config = self.config_manager.get_config().get("yasumi_clock", {})
        self.is_debug = self.yasumi_clock_config.get('debug', False)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_timer)

        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self._trigger_idle_reminder)
        
        self.time_remaining = QTime(0, 0)
        # 优先从每日进度文件中加载番茄钟计数
        self.pomodoro_count = config_manager.load_daily_pomodoro_count()
        
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
        self.log_file_path = self.config_manager.user_data_dir / "pomodoro_log.csv"

        # --- 休眠检测相关（仅 macOS）---
        self.sleep_timestamp = None  # 记录休眠前的时间戳

        # --- State Machine ---
        self.state = IdleState(self)
        self.apply_config() # 1. 应用基本配置
        
        # 2. 尝试恢复会话
        was_restored = self._restore_session_state()

        # 3. 如果没有恢复成功，则按配置进入默认的 Idle 状态
        if not was_restored:
            advanced_enabled = self.yasumi_clock_config.get("advanced_mode_enabled", False)
            if advanced_enabled:
                mode_key = self.yasumi_clock_config.get("active_mode_key", OperatingMode.CUSTOM.value)
                self.set_mode(OperatingMode.from_key(mode_key))
            else:
                self.set_mode(OperatingMode.CLASSIC)
            
            # 确保 UI 在启动时获得正确的 pomodoro_count
            self.pomodoro_completed.emit(self.pomodoro_count)

        # 初始化休眠监听器（仅 macOS）
        self._setup_sleep_watcher()


    def apply_config(self):
        """仅从ConfigManager加载配置并更新内部变量，不重置状态。"""
        config = self.config_manager.get_config()
        self.yasumi_clock_config = config.get("yasumi_clock", {})
        self.is_debug = self.yasumi_clock_config.get('debug', False)

    def reload_config_and_reset(self):
        """
        从设置窗口调用：重新加载配置并重置计时器状态。
        """
        self.apply_config()
        
        # 根据新配置设置模式
        advanced_enabled = self.yasumi_clock_config.get("advanced_mode_enabled", False)
        if advanced_enabled:
            mode_key = self.yasumi_clock_config.get("active_mode_key", OperatingMode.CUSTOM.value)
            self.set_mode(OperatingMode.from_key(mode_key))
        else:
            self.set_mode(OperatingMode.CLASSIC)

        # 检查是否需要重启空闲计时器
        if isinstance(self.state, IdleState):
            self._start_or_stop_idle_timer()

        # 重置状态以应用更改
        self.reset()

    def reload_config_without_reset(self):
        """
        仅重新加载配置而不重置计时器状态，用于不影响计时的设置项。
        """

        self.apply_config()
        # 检查是否需要重启空闲计时器
        if isinstance(self.state, IdleState):
            self._start_or_stop_idle_timer()

    def set_mode(self, mode: OperatingMode):
        """设置当前的操作模式。"""
        # 如果模式没有改变，并且计时器正在运行，则不执行任何操作，以防止重置
        if self.active_mode == mode and self.state.name != 'IDLE':
            return

        self.active_mode = mode
        # 只有在模式真正改变且计时器在运行时才重置
        if self.active_mode != mode and self.state.name != 'IDLE':
             self.reset()

        if mode == OperatingMode.CLASSIC:
            self.pomodoro_config = {}
            if self.is_debug:
                logging.debug("--- DEBUG MODE ON: Classic mode timer will be 5 seconds upon starting. ---")
            time_str = self.total_time_classic[self.time_index_classic]
            self.time_remaining, _ = self._parse_time(time_str)
            self.state_changed.emit(self.state.name, time_str, "调整时长后点击开始")
        else:
            preset_key = mode.value if mode != OperatingMode.CUSTOM else 'custom'
            self.pomodoro_config = self.yasumi_clock_config.get('presets', {}).get(preset_key, {})
            
            if self.is_debug:
                logging.debug("--- DEBUG MODE ON: Timers will be set to 5 seconds upon starting. ---")

            work_mins_config = self.pomodoro_config.get('work_mins', 25)
            if isinstance(work_mins_config, list):
                initial_work_mins = work_mins_config[0] if work_mins_config else 25
            else:
                initial_work_mins = work_mins_config
            
            time_str = f"{int(initial_work_mins):02d}:{int((initial_work_mins*60)%60):02d}"
            self.time_remaining, _ = self._parse_time(time_str)
            self.state_changed.emit(self.state.name, "Begin!", "准备开始专注工作")
        
        # 只有在空闲时才重置计数
        # 每当模式设置被调用时（包括重载配置），都应该同步当前的完成计数到UI，
        # 而不是无条件地重置它。真正的重置操作应该由 reset() 方法处理。
        if self.state.name == 'IDLE':
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
        self.config_manager.save_session_state(None) # 清除正在进行的会话状态
        self.pomodoro_count = 0
        self.config_manager.save_daily_pomodoro_count(self.pomodoro_count) # 重置每日进度
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
        logging.info(f"Engine state transition: {type(self.state).__name__} -> {type(new_state).__name__}")
        self.state = new_state
        self.state.enter_state()

        # Handle idle timer based on state transition
        self._start_or_stop_idle_timer()

    def start_countdown(self, time_str: str):
        """根据给定的时间字符串开始倒计时。"""
        try:
            self.time_remaining, total_seconds = self._parse_time(time_str)
            self.timer.start(1000)
        except ValueError:
            logging.error(f"Invalid time format for countdown: {time_str}")

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

    def _start_or_stop_idle_timer(self):
        """根据当前状态和配置启动或停止空闲计时器。"""
        idle_config = self.yasumi_clock_config.get("idle_reminder", {})
        is_enabled = idle_config.get("enabled", False)

        if isinstance(self.state, IdleState) and is_enabled:
            # 只有当计时器没有在运行时，才根据主阈值启动它
            if not self.idle_timer.isActive():
                # 无论是否在调试模式下，都使用相同的超时逻辑
                threshold_mins_key = "threshold_mins_debug" if self.is_debug else "threshold_mins"
                default_threshold = 0.25 if self.is_debug else 5  # 15秒用于调试，5分钟用于常规
                
                threshold_mins = idle_config.get(threshold_mins_key, default_threshold)
                timeout_ms = int(threshold_mins * 60 * 1000)
                
                logging.info(f"Idle timer started for {threshold_mins} minutes" + (" (DEBUG MODE)." if self.is_debug else "."))
                self.idle_timer.start(timeout_ms)
        else:
            if self.idle_timer.isActive():
                self.idle_timer.stop()
                logging.info("Idle timer stopped.")

    def _trigger_idle_reminder(self):
        """当空闲计时器到期时触发提醒。"""
        logging.info("Idle reminder triggered.")
        self.idle_reminder_triggered.emit()

        # 检查是否需要强力提醒
        idle_config = self.yasumi_clock_config.get("idle_reminder", {})
        if idle_config.get("forceful_reminder", False):
            # 如果是强力模式，则设置一个较短的重复提醒间隔
            if self.is_debug:
                follow_up_ms = 10000 # 10 seconds for debug
                logging.debug("Forceful reminder re-armed for 10 seconds (DEBUG MODE).")
            else:
                interval_mins = idle_config.get("forceful_interval_mins", 2)
                follow_up_ms = interval_mins * 60 * 1000
                logging.info(f"Forceful reminder re-armed for {interval_mins} minutes.")
            self.idle_timer.start(follow_up_ms)

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
        
        pomodoro_logger.log_session(session_data, self.log_file_path)
        
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
        logging.info("Break interrupted by user.")

    def get_session_state(self) -> dict | None:
        """
        获取当前会话的状态，用于持久化。
        如果当前是空闲状态，则不应保存，返回 None。
        """
        if isinstance(self.state, IdleState):
            return None
        
        total_seconds = self.time_remaining.minute() * 60 + self.time_remaining.second()

        state_to_save = self.state
        # 如果是暂停状态, 我们要保存的是暂停之前的状态
        if isinstance(self.state, PausedState):
            state_to_save = self.state.previous_state

        return {
            'state_name': state_to_save.name,
            'time_remaining_seconds': total_seconds,
            'pomodoro_count': self.pomodoro_count,
            'is_paused': isinstance(self.state, PausedState),
            'active_mode': self.active_mode.value # 保存当前模式
        }

    def _restore_session_state(self) -> bool:
        """
        在引擎启动时尝试从配置文件恢复会话状态。
        成功恢复则返回 True，否则返回 False。
        """
        # 首先检查用户设置是否允许恢复会话
        if not self.yasumi_clock_config.get("resume_unfinished_session", True):
            return False

        state_data = self.config_manager.load_session_state()
        if not state_data:
            return False

        logging.info(f"Restoring session state: {state_data}")

        try:
            # 1. 恢复模式
            # 注意：在调用 set_mode 之前应用配置，以确保 pomodoro_config 被正确加载
            self.apply_config()
            mode_key = state_data.get('active_mode', OperatingMode.CLASSIC.value)
            self.set_mode(OperatingMode.from_key(mode_key))

            # 2. 计算剩余时间
            remaining_seconds = int(state_data['time_remaining_seconds'])
            elapsed_seconds = int(state_data.get('elapsed_seconds_since_save', 0))
            actual_remaining_seconds = remaining_seconds - elapsed_seconds

            # 宽限期逻辑：如果保存时剩余时间就很少（少于10秒），则忽略关闭期间流逝的时间
            GRACE_PERIOD_SECONDS = 10
            if remaining_seconds < GRACE_PERIOD_SECONDS:
                logging.info(f"Remaining time ({remaining_seconds}s) is within grace period. Ignoring elapsed time.")
                actual_remaining_seconds = remaining_seconds
            
            # 3. 恢复状态变量（提前，因为模拟结束时需要用到）
            self.pomodoro_count = int(state_data['pomodoro_count'])
            state_name = state_data['state_name']

            if actual_remaining_seconds <= 0:
                logging.info("Timer finished while app was closed. Simulating completion...")
                # 清除旧的会话状态
                self.config_manager.save_session_state(None)

                # 实例化计时器结束前的状态
                state_map_for_finish = { 'WORKING': WorkingState, 'SHORT_BREAK': ShortBreakState, 'LONG_BREAK': LongBreakState }
                if self.active_mode == OperatingMode.CLASSIC and state_name == 'SHORT_BREAK':
                    target_state_class = ClassicBreakState
                else:
                    target_state_class = state_map_for_finish.get(state_name)

                if target_state_class:
                    # 创建临时状态对象并手动调用其完成处理程序
                    finished_state = target_state_class(self)
                    finished_state.handle_timer_finish()
                    logging.info(f"Simulated '{state_name}' completion, transitioned to '{self.state.name}'.")
                    return True # 恢复（通过模拟完成）成功
                else:
                    logging.warning(f"Cannot simulate finish for unknown state '{state_name}'.")
                    return False

            # --- 如果计时器没有在关闭期间结束，则正常恢复 ---
            minutes, seconds = divmod(actual_remaining_seconds, 60)
            self.time_remaining = QTime(0, int(minutes), int(seconds))

            # 4. 确定要恢复的状态
            is_paused = state_data.get('is_paused', False)

            state_map = {
                'WORKING': WorkingState, 'SHORT_BREAK': ShortBreakState,
                'LONG_BREAK': LongBreakState
            }
            
            target_state_class = state_map.get(state_name)
            if self.active_mode == OperatingMode.CLASSIC and state_name == 'SHORT_BREAK':
                target_state_class = ClassicBreakState
            
            if not target_state_class:
                logging.warning(f"Unknown state name '{state_name}' found. Cannot restore.")
                return False

            # 5. 实例化并设置状态
            restored_state = target_state_class(self)
            self.state = restored_state
            
            # 6. 手动触发UI更新
            time_str = self.time_remaining.toString("mm:ss")
            next_up_text = ""
            if isinstance(restored_state, WorkingState):
                self.animation_change_requested.emit("work")
                is_next_long_break = (self.pomodoro_count + 1) >= self.pomodoro_config.get('cycles_before_long_break', 4)
                next_up_text = "下一步：长休息" if is_next_long_break else "下一步：短休息"
            elif isinstance(restored_state, (ShortBreakState, LongBreakState, ClassicBreakState)):
                self.animation_change_requested.emit("play")
                next_up_text = "下一步：专注工作"

            # 7. 使用 QTimer.singleShot 延迟启动计时器和UI更新
            # 这给予了主窗口足够的时间来渲染，避免了UI不同步和“跳秒”的问题
            def finalize_restore():
                # 根据用户建议，恢复时总是进入暂停状态，等待用户手动开始
                self.transition_to_state(PausedState(self, restored_state))

                # 发射 pomodoro_completed 信号以确保UI上的进度点正确更新
                self.pomodoro_completed.emit(self.pomodoro_count)
                logging.info(f"Finalized session restore to {self.state.name} with {time_str} remaining. Waiting for user to continue.")

            QTimer.singleShot(800, finalize_restore)
            return True

        except Exception as e:
            logging.error(f"Failed to restore session state: {e}", exc_info=True)
            self.config_manager.save_session_state(None)
            return False

    def _setup_sleep_watcher(self):
        """
        设置 macOS 系统休眠/唤醒监听器。
        仅在 macOS 平台且 pyobjc 可用时启用。
        """
        # 平台检查
        if platform.system() != "Darwin":
            logging.debug("Not macOS, sleep detection disabled")
            return

        # pyobjc 可用性检查
        try:
            from Foundation import NSNotificationCenter
            from AppKit import NSWorkspace
        except ImportError:
            logging.warning("pyobjc not available, sleep detection disabled")
            return

        try:
            # 获取共享的 NSWorkspace 实例
            workspace = NSWorkspace.sharedWorkspace()
            nc = workspace.notificationCenter()

            # 注册休眠通知
            nc.addObserver_selector_name_object_(
                self,
                'onSystemWillSleep:',
                'NSWorkspaceWillSleepNotification',
                None
            )

            # 注册唤醒通知
            nc.addObserver_selector_name_object_(
                self,
                'onSystemDidWake:',
                'NSWorkspaceDidWakeNotification',
                None
            )

            logging.info("macOS sleep/wake detection enabled successfully")

        except Exception as e:
            logging.error(f"Failed to setup sleep watcher: {e}", exc_info=True)

    def onSystemWillSleep_(self, notification):
        """
        系统即将休眠时的回调。
        记录当前时间戳，用于唤醒后计算实际经过时间。

        注意：方法名必须匹配 Objective-C 选择器格式（末尾有下划线）
        """
        self.sleep_timestamp = datetime.now()
        logging.info(f"System will sleep at {self.sleep_timestamp.isoformat()}")

    def onSystemDidWake_(self, notification):
        """
        系统唤醒后的回调。
        计算实际经过时间并调整计时器状态。

        注意：方法名必须匹配 Objective-C 选择器格式（末尾有下划线）
        """
        wake_time = datetime.now()
        logging.info(f"System did wake at {wake_time.isoformat()}")

        # 检查是否有有效的休眠时间戳
        if not self.sleep_timestamp:
            logging.warning("No sleep timestamp found, skipping time compensation")
            return

        # 计算实际经过的时间
        elapsed_time = wake_time - self.sleep_timestamp
        elapsed_seconds = int(elapsed_time.total_seconds())
        logging.info(f"System was asleep for {elapsed_seconds} seconds")

        # 清除休眠时间戳
        self.sleep_timestamp = None

        # 只处理活动状态（非空闲、非暂停）
        if isinstance(self.state, IdleState):
            logging.debug("Currently in IdleState, no time compensation needed")
            return

        if isinstance(self.state, PausedState):
            logging.debug("Currently in PausedState, no time compensation needed")
            return

        # 计算当前剩余时间（秒）
        current_remaining_seconds = self.time_remaining.minute() * 60 + self.time_remaining.second()
        logging.debug(f"Current remaining time: {current_remaining_seconds} seconds")

        # 计算补偿后的剩余时间
        new_remaining_seconds = current_remaining_seconds - elapsed_seconds
        logging.debug(f"New remaining time after compensation: {new_remaining_seconds} seconds")

        if new_remaining_seconds <= 0:
            # 时间已到，直接触发完成逻辑
            logging.info("Timer expired during sleep, triggering completion")
            self.timer.stop()
            self.last_minute_tick.emit("00:00", False)  # 隐藏悬浮窗
            self.state.handle_timer_finish()
        else:
            # 调整剩余时间
            minutes, seconds = divmod(new_remaining_seconds, 60)
            self.time_remaining = QTime(0, int(minutes), int(seconds))

            # 更新 UI
            time_str = self.time_remaining.toString("mm:ss")
            logging.info(f"Adjusted remaining time to {time_str}")

            # 根据状态发送不同的信号
            if isinstance(self.state, WorkingState):
                self.time_updated.emit(time_str)

                # 检查是否需要显示最后一分钟悬浮窗
                show_last_minute_window = self.yasumi_clock_config.get("show_last_minute_window", False)
                if show_last_minute_window and new_remaining_seconds <= 60:
                    self.last_minute_tick.emit(time_str, True)

            elif isinstance(self.state, (ShortBreakState, LongBreakState, ClassicBreakState)):
                # 休息状态不更新主窗口时间，但需要确保计时器继续运行
                logging.debug("Break state time adjusted, timer continues")

