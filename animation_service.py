import logging
from PyQt5.QtCore import QObject
from MainWindowThread import DrawAnimationThread
from util import ConfigManager

class AnimationService(QObject):
    """
    统一管理应用程序的动画播放服务。
    """
    def __init__(self, config_manager: ConfigManager, animation_label, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.animation_label = animation_label
        
        self.work_thread = None
        self.play_thread = None

        self._load_config()

    def _load_config(self):
        """加载动画相关的配置。"""
        config = self.config_manager.get_config()
        src_config = self.config_manager.get_src_config()
        
        main_window_config = config.get("yasumi_clock", {}).get("main_window", {})
        self.animation_pos = main_window_config.get("animation")
        
        self.play_path = self.config_manager.get_resource_path(src_config.get("play"))
        self.work_path = self.config_manager.get_resource_path(src_config.get("work"))

    def change_animation(self, animation_type: str):
        """
        切换动画。
        :param animation_type: "work" 或 "play"
        """
        if animation_type == "work":
            self._stop_thread(self.play_thread)
            self.play_thread = None
            self.work_thread = self._start_thread_if_not_running(self.work_thread, self.work_path)
        elif animation_type == "play":
            self._stop_thread(self.work_thread)
            self.work_thread = None
            self.play_thread = self._start_thread_if_not_running(self.play_thread, self.play_path)

    def _start_thread_if_not_running(self, thread: DrawAnimationThread, path: str) -> DrawAnimationThread:
        """如果线程未运行，则启动它。"""
        if thread and thread.isRunning():
            return thread
        
        new_thread = DrawAnimationThread()
        new_thread.setup(
            path=path,
            label=self.animation_label,
            pos=self.animation_pos,
            frame_speed=30
        )
        new_thread.start()
        return new_thread

    def _stop_thread(self, thread: DrawAnimationThread):
        """如果线程正在运行，则停止它。"""
        if thread and thread.isRunning():
            try:
                thread.stop()
                # 添加2秒超时，避免无限期等待
                if not thread.wait(2000):  # 等待最多2秒
                    logging.warning("动画线程未能在2秒内停止，强制继续。")
                    # 如果线程仍在运行，尝试强制终止
                    if thread.isRunning():
                        thread.terminate()
                        thread.wait(1000)  # 再等1秒
                        if thread.isRunning():
                            logging.error("无法停止动画线程，将继续执行。")
            except Exception as e:
                logging.error(f"停止动画线程时发生错误: {str(e)}")

    def stop_all(self):
        """停止所有动画线程。"""
        self._stop_thread(self.work_thread)
