from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from PyQt5.QtGui import QIcon
from datetime import timedelta
from datetime import datetime

if TYPE_CHECKING:
    from pomodoro_engine import PomodoroEngine
    from mode_enums import OperatingMode

class PomodoroState(ABC):
    """状态模式的抽象基类。"""

    name: str = "UNKNOWN"

    def __init__(self, context: PomodoroEngine):
        self.context = context

    @abstractmethod
    def handle_timer_finish(self):
        """处理计时器完成事件的逻辑。"""
        pass

    def enter_state(self):
        """进入此状态时执行的逻辑。"""
        # UI更新现在由引擎的信号驱动，状态类本身不直接操作UI
        pass

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
        from mode_enums import OperatingMode
        if self.context.active_mode == OperatingMode.CLASSIC:
            time_str = self.context.total_time_classic[self.context.time_index_classic]
            next_up = "调整时长后点击开始"
        else:
            work_mins = self.context.pomodoro_config.get('work_mins', 25)
            time_str = f"{work_mins:02d}:00"
            next_up = "准备开始专注工作"
        
        self.context.time_remaining, _ = self.context._parse_time(time_str)
        self.context.state_changed.emit(self.name, time_str if self.context.active_mode == OperatingMode.CLASSIC else "Begin!", next_up)
        self.context.animation_change_requested.emit("play")
        super().enter_state()

class WorkingState(PomodoroState):
    """工作状态。"""
    name = 'WORKING'
    def handle_timer_finish(self):
        self.context._log_session(status='completed')
        self.context.pomodoro_count += 1
        self.context.pomodoro_completed.emit(self.context.pomodoro_count)
        
        is_long_break_time = self.context.pomodoro_count >= self.context.pomodoro_config.get('cycles_before_long_break', 4)

        next_state = LongBreakState(self.context) if is_long_break_time else ShortBreakState(self.context)
        self.context.transition_to_state(next_state)

    def enter_state(self):
        self.context.animation_change_requested.emit("work")
        
        is_debug = self.context.yasumi_clock_config.get('debug', False)
        work_mins = 0.08 if is_debug else self.context.pomodoro_config.get('work_mins', 25)
        time_to_start = "00:05" if is_debug else f"{work_mins:02d}:00"

        # --- Log session start ---
        self.context.session_start_time = datetime.now()
        self.context.session_type = 'pomodoro'
        self.context.session_planned_duration_minutes = work_mins
        self.context.session_total_pause_duration = timedelta(0)
        self.context.session_pause_count = 0
        
        self.context.start_countdown(time_to_start)
        
        is_next_long_break = (self.context.pomodoro_count + 1) >= self.context.pomodoro_config.get('cycles_before_long_break', 4)
        next_up = "下一步：长休息" if is_next_long_break else "下一步：短休息"
        
        self.context.state_changed.emit(self.name, time_to_start, next_up)
        super().enter_state()


class BreakState(PomodoroState):
    """休息状态的基类。"""
    def __init__(self, context: PomodoroEngine, is_classic_break: bool = False):
        super().__init__(context)
        self.is_classic_break = is_classic_break

    def enter_state(self):
        self.context.animation_change_requested.emit("play")
        self.context.long_break_started.emit() # Signal to show the break window
        
        self.context.state_changed.emit(self.name, "", "下一步：专注工作")
        super().enter_state()

    def handle_timer_finish(self):
        self.context._log_session(status='completed')
        self.context.play_sound_requested.emit()
        self.context.break_finished.emit() # Signal to close the break window
        
        # 休息结束后，回到空闲状态，等待用户操作
        self.context.transition_to_state(IdleState(self.context))


class ShortBreakState(BreakState):
    """短休息状态。"""
    name = 'SHORT_BREAK'
    def enter_state(self):
        super().enter_state()
        
        is_debug = self.context.yasumi_clock_config.get('debug', False)
        break_mins = 0.08 if is_debug else self.context.pomodoro_config.get('short_break_mins', 5)
        break_time_str = "00:05" if is_debug else f"{break_mins:02d}:00"

        # --- Log session start ---
        self.context.session_start_time = datetime.now()
        self.context.session_type = 'short_break'
        self.context.session_planned_duration_minutes = break_mins
        self.context.session_total_pause_duration = timedelta(0)
        self.context.session_pause_count = 0
            
        self.context.start_countdown(break_time_str)


class LongBreakState(BreakState):
    """长休息状态。"""
    name = 'LONG_BREAK'
    def enter_state(self):
        self.context.pomodoro_count = 0
        self.context.pomodoro_completed.emit(self.context.pomodoro_count)
        super().enter_state()
        
        is_debug = self.context.yasumi_clock_config.get('debug', False)
        break_mins = 0.08 if is_debug else self.context.pomodoro_config.get('long_break_mins', 15)
        break_time_str = "00:05" if is_debug else f"{break_mins:02d}:00"

        # --- Log session start ---
        self.context.session_start_time = datetime.now()
        self.context.session_type = 'long_break'
        self.context.session_planned_duration_minutes = break_mins
        self.context.session_total_pause_duration = timedelta(0)
        self.context.session_pause_count = 0
            
        self.context.start_countdown(break_time_str)


class PausedState(PomodoroState):
    """暂停状态。"""
    name = 'PAUSED'
    def __init__(self, context: PomodoroEngine, previous_state: PomodoroState):
        super().__init__(context)
        self.previous_state = previous_state

    def handle_timer_finish(self):
        # 暂停状态不应该有计时器完成事件
        pass

    def enter_state(self):
        self.context.pause_start_time = datetime.now()
        self.context.session_pause_count += 1
        
        time_str = self.context.time_remaining.toString("mm:ss")
        self.context.state_changed.emit(self.name, time_str, "已暂停")
        super().enter_state()

    def exit_state(self):
        """恢复时调用的方法"""
        if self.context.pause_start_time:
            pause_duration = datetime.now() - self.context.pause_start_time
            self.context.session_total_pause_duration += pause_duration
            self.context.pause_start_time = None

        # 恢复到之前的状态
        self.context.state = self.previous_state
        
        # 根据恢复到的状态，确定正确的“下一步”文本
        next_up_text = ""
        if isinstance(self.previous_state, WorkingState):
            is_next_long_break = (self.context.pomodoro_count + 1) >= self.context.pomodoro_config.get('cycles_before_long_break', 4)
            next_up_text = "下一步：长休息" if is_next_long_break else "下一步：短休息"
        elif isinstance(self.previous_state, BreakState):
            next_up_text = "下一步：专注工作"

        # 发射信号以更新UI
        time_str = self.context.time_remaining.toString("mm:ss")
        self.context.state_changed.emit(self.previous_state.name, time_str, next_up_text)