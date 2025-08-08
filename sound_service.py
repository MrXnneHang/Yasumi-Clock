import os
from PyQt5.QtCore import QObject, pyqtSignal
from util import SoundPlayer, ConfigManager
from StopSoundWindow import StopSoundWindow

class SoundService(QObject):
    """
    统一管理应用程序的声音播放服务。
    """
    sound_finished = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.player = SoundPlayer()
        self.stop_sound_window = None

        self.player.playback_finished.connect(self.on_playback_finished)

    def play_notification(self):
        """
        根据配置播放通知声音。
        """
        config = self.config_manager.get_config()
        notification_config = config.get("yasumi_clock", {}).get("notification", {})

        if not notification_config.get("enabled", False):
            print("通知功能已禁用。")
            self.sound_finished.emit()
            return

        if self.stop_sound_window:
            self.stop_sound_window.close()
        
        # 总是显示停止按钮，因为声音可能会循环播放
        self.stop_sound_window = StopSoundWindow(stop_callback=self.player.stop)
        self.stop_sound_window.show()

        src_config = self.config_manager.get_src_config()
        sound_key = notification_config.get("sound", "default")
        sound_rel_path = src_config.get("notification_sounds", {}).get(sound_key)

        if not sound_rel_path:
            print(f"错误：在 src.yml 中找不到声音键 '{sound_key}'。")
            self.on_playback_finished()
            return
        
        sound_abs_path = self.config_manager.get_resource_path(sound_rel_path)
        if not os.path.exists(sound_abs_path):
            print(f"错误：找不到音频文件: {sound_abs_path}")
            self.on_playback_finished()
            return

        mode = notification_config.get("mode", "play_once")
        loop_count = notification_config.get("loop_count", 3)
        loop_map = {"loop_play": -1, "loop_n_times": loop_count}
        loop_count_for_player = loop_map.get(mode, 1)
        
        volume = notification_config.get("volume", 80)
        device_id = notification_config.get("output_device_id", -1)
        device_to_use = device_id if device_id != -1 else None

        self.player.play(sound_abs_path, volume, loop_count_for_player, device_to_use)

    def on_playback_finished(self):
        """当播放完成或被停止时，清理资源。"""
        if self.stop_sound_window:
            self.stop_sound_window.close()
            self.stop_sound_window = None
        self.sound_finished.emit()

    def stop(self):
        """停止所有声音。"""
        self.player.stop()
