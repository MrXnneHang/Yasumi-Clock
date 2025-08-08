from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from PyQt5.QtGui import QIcon
from datetime import timedelta
from datetime import datetime

if TYPE_CHECKING:
    from yasumi_clock import Main_Window_Response
    from mode_enums import OperatingMode

class PomodoroState(ABC):
    """状态模式的抽象基类。"""

    name: str = "UNKNOWN"

    def __init__(self, context: Main_Window_Response):
        self.context = context

    @abstractmethod
    def handle_timer_finish(self):
        """处理计时器完成事件的逻辑。"""
        pass

    def enter_state(self):
        """进入此状态时执行的逻辑。"""
        self.context._update_status_display()

    def get_next_state(self) -> PomodoroState:
        """默认情况下，状态不会自动转换。"""
        return self

class IdleState(PomodoroState):
    """空闲状态。"""
    name = 'IDLE'
    def handle_timer_finish(self):
        # 空闲状态不应该处理计时器完成，但为了健壮性，我们可以在这里添加日志
        print("警告：计时器在 IdleState 中完成。")

    def enter_state(self):
        self.context.current_state_str = self.name
        self.context.timerRunning = False
        # 根据模式显示不同的时间文本
        from mode_enums import OperatingMode
        if self.context.active_mode == OperatingMode.CLASSIC:
            # 经典模式：直接显示当前设置的倒计时时间
            current_time = self.context.total_time_classic[self.context.time_index_classic]
            self.context.crossfade_text(self.context.timeLabel, current_time)
        else:
            # 其他模式：显示 "Begin!"
            self.context.crossfade_text(self.context.timeLabel, "Begin!")
        self.context.startFanqieButton.setText("开始")
        # 根据模式显示不同的默认提示
        if self.context.active_mode == OperatingMode.CLASSIC:
            self.context.nextUpLabel.setText("调整时长后点击开始")
        else:
            self.context.nextUpLabel.setText("准备开始专注工作")
        super().enter_state()

class WorkingState(PomodoroState):
    """工作状态。"""
    name = 'WORKING'
    def handle_timer_finish(self):
        self.context._log_session(status='completed') # 记录完成的工作会话
        self.context.pomodoro_count += 1
        
        is_long_break_time = self.context.pomodoro_count >= self.context.pomodoro_config.get('cycles_before_long_break', 4)

        if is_long_break_time:
            self.context.transition_to_state(LongBreakState(self.context))
        else:
            self.context.transition_to_state(ShortBreakState(self.context))

    def enter_state(self):
        self.context.current_state_str = self.name
        self.context.timerRunning = True
        self.context.change_animation(action="work")
        
        is_debug = self.context.yasumi_clock_config.get('debug', False)
        if is_debug:
            time_to_start = "00:05"
            work_mins = 0.08 # 5 seconds for debug
        else:
            work_mins = self.context.pomodoro_config.get('work_mins', 25)
            time_to_start = f"{work_mins:02d}:00"

        # --- Log session start ---
        self.context.session_start_time = datetime.now()
        self.context.session_type = 'pomodoro'
        self.context.session_planned_duration_minutes = work_mins
        self.context.session_total_pause_duration = timedelta(0)
        self.context.session_pause_count = 0
        # --- End log session start ---
            
        self.context.startCountdown(time_to_start)
        self.context.startFanqieButton.setText("暂停") # <--- 新增
        # 判断下一次是长休息还是短休息
        is_next_long_break = (self.context.pomodoro_count + 1) >= self.context.pomodoro_config.get('cycles_before_long_break', 4)
        if is_next_long_break:
            self.context.nextUpLabel.setText("下一步：长休息")
        else:
            self.context.nextUpLabel.setText("下一步：短休息")
        super().enter_state()


class BreakState(PomodoroState):
    """休息状态的基类。"""
    def __init__(self, context: Main_Window_Response, is_classic_break: bool = False):
        super().__init__(context)
        self.is_classic_break = is_classic_break

    def enter_state(self):
        self.context.timerRunning = True
        self.context.change_animation(action="play")
        
        # 弹出休息窗口
        if self.context.yasumi:
            self.context.yasumi.close()
        
        # 动态导入以避免循环依赖
        from yasumi_window import yasumiWindow
        from util import combine_path

        self.context.yasumi = yasumiWindow(self.context)
        icon_path = combine_path(self.context.absolute_dir, self.context.src_config["icon"])
        self.context.yasumi.setWindowIcon(QIcon(icon_path))
        self.context.yasumi.finished.connect(self.context.on_yasumi_window_closed)
        self.context.yasumi.show()

        # 休息时隐藏主窗口的计时器和提示
        self.context.timeLabel.setText("")
        self.context.nextUpLabel.setText("")

        self.context.startFanqieButton.setText("暂停") # 休息状态下也支持暂停功能
        
        # 让“跳过”按钮真正生效
        # 先断开旧连接，再连接新功能
        # 保持原有的按钮连接，不需要重新连接

        self.context.nextUpLabel.setText("下一步：专注工作")
        super().enter_state()

    def handle_timer_finish(self):
        self.context._log_session(status='completed') # 记录完成的休息会话
        # 休息结束后，播放提示音并回到工作状态
        self.context.play_notification_sound()
        
        if self.context.yasumi and self.context.yasumi.isVisible():
            try:
                self.context.yasumi.finished.disconnect(self.context.on_yasumi_window_closed)
            except TypeError:
                pass
            self.context.yasumi.close()
            self.context.yasumi = None
        
        # 休息结束后，自动开始下一个工作周期
        self.context.transition_to_state(IdleState(self.context))


class ShortBreakState(BreakState):
    """短休息状态。"""
    name = 'SHORT_BREAK'
    def enter_state(self):
        self.context.current_state_str = self.name
        super().enter_state() # 处理公共的休息逻辑
        
        is_debug = self.context.yasumi_clock_config.get('debug', False)
        if is_debug:
            break_time_str = "00:05"
            break_mins = 0.08 # 5 seconds for debug
        else:
            if self.is_classic_break:
                # 经典模式下的休息时间
                config = self.context.yasumi_clock_config.get('presets', {}).get('custom', {})
                break_mins = config.get('short_break_mins', 5)
            else:
                # 番茄钟模式下的短休息
                break_mins = self.context.pomodoro_config.get('short_break_mins', 5)
            break_time_str = f"{break_mins:02d}:00"

        # --- Log session start ---
        self.context.session_start_time = datetime.now()
        self.context.session_type = 'short_break'
        self.context.session_planned_duration_minutes = break_mins
        self.context.session_total_pause_duration = timedelta(0)
        self.context.session_pause_count = 0
        # --- End log session start ---
            
        self.context.startCountdown(break_time_str)


class LongBreakState(BreakState):
    """长休息状态。"""
    name = 'LONG_BREAK'
    def enter_state(self):
        self.context.current_state_str = self.name
        self.context.pomodoro_count = 0  # 长休息开始时重置计数器
        super().enter_state()
        
        is_debug = self.context.yasumi_clock_config.get('debug', False)
        if is_debug:
            break_time_str = "00:05"
            break_mins = 0.08 # 5 seconds for debug
        else:
            break_mins = self.context.pomodoro_config.get('long_break_mins', 15)
            break_time_str = f"{break_mins:02d}:00"

        # --- Log session start ---
        self.context.session_start_time = datetime.now()
        self.context.session_type = 'long_break'
        self.context.session_planned_duration_minutes = break_mins
        self.context.session_total_pause_duration = timedelta(0)
        self.context.session_pause_count = 0
        # --- End log session start ---
            
        self.context.startCountdown(break_time_str)


class PausedState(PomodoroState):
    """暂停状态。"""
    name = 'PAUSED'
    def __init__(self, context: Main_Window_Response, previous_state: PomodoroState):
        super().__init__(context)
        self.previous_state = previous_state

    def handle_timer_finish(self):
        # 暂停状态不应该有计时器完成事件
        pass

    def enter_state(self):
        self.context.current_state_str = self.name
        self.context.timerRunning = False
        self.context.startFanqieButton.setText("继续")
        self.context.pause_start_time = datetime.now()
        self.context.session_pause_count += 1
        # 可选：增加一个视觉提示，比如让计时器文本变暗
        self.context.timeLabel.setStyleSheet(self.context.timeLabel.styleSheet() + " color: #A9A9A9;")
        super().enter_state()

    def exit_state(self):
        """恢复时调用的方法"""
        # 恢复UI
        self.context.timeLabel.setStyleSheet(self.context.timeLabel.styleSheet().replace(" color: #A9A9A9;", ""))
        self.context.startFanqieButton.setText("暂停")

        # 计算暂停时长并累加
        if self.context.pause_start_time:
            pause_duration = datetime.now() - self.context.pause_start_time
            self.context.session_total_pause_duration += pause_duration
            self.context.pause_start_time = None

        # 恢复内部状态
        self.context.timerRunning = True
        
        # 核心：直接恢复状态对象，绕过会重置计时的 enter_state
        self.context.state = self.previous_state
        self.context.current_state_str = self.previous_state.name
        
        # 更新一下状态显示
        self.context._update_status_display()