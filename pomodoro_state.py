from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from PyQt5.QtGui import QIcon

if TYPE_CHECKING:
    from yasumi_clock import Main_Window_Response
    from mode_enums import OperatingMode

class PomodoroState(ABC):
    """状态模式的抽象基类。"""

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
    def handle_timer_finish(self):
        # 在经典模式下，计时结束后进入标准短休息
        self.context.timeLabel.setText("完成!")
        self.context.change_animation(action="play")
        self.context.transition_to_state(ShortBreakState(self.context, is_classic_break=True))

    def enter_state(self):
        self.context.current_state_str = 'IDLE'
        self.context.timerRunning = False
        self.context.timeLabel.setText("Begin!")
        super().enter_state()

class WorkingState(PomodoroState):
    """工作状态。"""
    def handle_timer_finish(self):
        self.context.pomodoro_count += 1
        
        is_long_break_time = self.context.pomodoro_count >= self.context.pomodoro_config.get('cycles_before_long_break', 4)

        if is_long_break_time:
            self.context.transition_to_state(LongBreakState(self.context))
        else:
            self.context.transition_to_state(ShortBreakState(self.context))

    def enter_state(self):
        self.context.current_state_str = 'WORKING'
        self.context.timerRunning = True
        self.context.change_animation(action="work")
        
        is_debug = self.context.yasumi_clock_config.get('debug', False)
        if is_debug:
            time_to_start = "00:05"
        else:
            work_mins = self.context.pomodoro_config.get('work_mins', 25)
            time_to_start = f"{work_mins:02d}:00"
            
        self.context.startCountdown(time_to_start)
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

        super().enter_state()

    def handle_timer_finish(self):
        # 休息结束后，播放提示音并回到空闲状态
        self.context.play_notification_sound()
        
        if self.context.yasumi and self.context.yasumi.isVisible():
            try:
                self.context.yasumi.finished.disconnect(self.context.on_yasumi_window_closed)
            except TypeError:
                pass
            self.context.yasumi.close()
            self.context.yasumi = None
        
        self.context.transition_to_state(IdleState(self.context))


class ShortBreakState(BreakState):
    """短休息状态。"""
    def enter_state(self):
        self.context.current_state_str = 'SHORT_BREAK'
        super().enter_state() # 处理公共的休息逻辑
        
        is_debug = self.context.yasumi_clock_config.get('debug', False)
        if is_debug:
            break_time_str = "00:05"
        else:
            if self.is_classic_break:
                # 经典模式下的休息时间
                config = self.context.yasumi_clock_config.get('presets', {}).get('custom', {})
                break_mins = config.get('short_break_mins', 5)
            else:
                # 番茄钟模式下的短休息
                break_mins = self.context.pomodoro_config.get('short_break_mins', 5)
            break_time_str = f"{break_mins:02d}:00"
            
        self.context.startCountdown(break_time_str)


class LongBreakState(BreakState):
    """长休息状态。"""
    def enter_state(self):
        self.context.current_state_str = 'LONG_BREAK'
        self.context.pomodoro_count = 0  # 长休息开始时重置计数器
        super().enter_state()
        
        is_debug = self.context.yasumi_clock_config.get('debug', False)
        if is_debug:
            break_time_str = "00:05"
        else:
            break_mins = self.context.pomodoro_config.get('long_break_mins', 15)
            break_time_str = f"{break_mins:02d}:00"
            
        self.context.startCountdown(break_time_str)