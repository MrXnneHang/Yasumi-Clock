import yaml
import os
import sys
import pathlib
from moviepy.editor import VideoFileClip
from PIL import Image
from PyQt5 import QtCore
import platform
import sounddevice as sd
import numpy as np
from pydub import AudioSegment

import threading

# --- Start of new ConfigManager ---
class ConfigManager:
    """
    统一管理应用程序的配置。
    加载、合并和提供对 yasumi_config.yml, user_config.yml 和 src.yml 的访问。
    处理资源路径解析和用户配置的保存。
    """
    def __init__(self):
        self.absolute_dir = self._get_absolute_dir()
        self.config = {}
        self.src_config = {}
        self._load_all_configs()

    def _get_absolute_dir(self):
        """ 获取资源的绝对路径，兼容源码运行和PyInstaller打包 """
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return pathlib.Path(sys._MEIPASS)
        else:
            return pathlib.Path(os.path.dirname(os.path.abspath(__file__)))

    def _deep_merge_dicts(self, d1, d2):
        """
        深度合并两个字典。
        - 如果键在d2中也存在于d1中，并且值都是字典，则递归合并。
        - 否则，d2中的值将覆盖d1中的值。
        """
        for k, v in d2.items():
            if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                d1[k] = self._deep_merge_dicts(d1[k], v)
            else:
                d1[k] = v
        return d1

    def _load_all_configs(self):
        """加载并合并所有YAML配置文件。"""
        # 定义配置文件路径
        default_config_path = self.absolute_dir / "yasumi_config.yml"
        user_config_path = self.absolute_dir / "user_config.yml"
        src_config_path = self.absolute_dir / "src.yml"

        # 加载默认配置
        if default_config_path.is_file():
            with open(default_config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file) or {}
        else:
            raise FileNotFoundError(f"默认配置文件未找到: {default_config_path}")

        # 加载并合并用户配置
        if user_config_path.is_file():
            with open(user_config_path, 'r', encoding='utf-8') as file:
                user_config = yaml.safe_load(file)
                if user_config:
                    self.config = self._deep_merge_dicts(self.config, user_config)

        # [新增] 检查 YASUMI_DEBUG 环境变量，覆盖 debug 设置
        debug_env = os.environ.get('YASUMI_DEBUG', '').lower()
        if debug_env == 'true':
            self.config.setdefault('yasumi_clock', {})['debug'] = True
        elif debug_env == 'false':
            self.config.setdefault('yasumi_clock', {})['debug'] = False
        
        # 加载资源配置
        if src_config_path.is_file():
            with open(src_config_path, 'r', encoding='utf-8') as file:
                self.src_config = yaml.safe_load(file) or {}
        else:
            raise FileNotFoundError(f"资源配置文件未找到: {src_config_path}")

    def get_config(self):
        """返回合并后的主配置 (yasumi_config + user_config)"""
        return self.config

    def get_src_config(self):
        """返回资源配置 (src.yml)"""
        return self.src_config

    def get_resource_path(self, rel_path: str) -> str:
        """根据相对路径获取资源的绝对路径字符串"""
        # 合并多重路径
        current_path = self.absolute_dir
        rel_paths = rel_path.split("/")
        for path_part in rel_paths:
            current_path = current_path / path_part
        return str(current_path)

    def save_user_config(self, data: dict):
        """将用户特定配置保存到 user_config.yml"""
        user_config_path = self.absolute_dir / "user_config.yml"
        with open(user_config_path, 'w', encoding='utf-8') as file:
            yaml.dump(data, file, allow_unicode=True, sort_keys=False)
        
        # 保存后立即重新加载配置，以确保内存中的配置是最新的
        self._load_all_configs()

# --- End of new ConfigManager ---


class SoundPlayer(QtCore.QObject):
    """一个可控制的音频播放器，支持播放、停止和循环。"""
    playback_finished = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.stream = None
        self.is_playing_flag = False
        self.lock = threading.Lock()
        self.playback_thread = None
        self.stop_event = threading.Event()

    def play(self, sound_path, volume=100, loop_count=1, device_id=None):
        """
        播放音频。
        :param sound_path: 音频文件路径。
        :param volume: 音量 (0-100)。
        :param loop_count: 循环次数。1表示播放一次, -1表示无限循环。
        :param device_id: 输出设备ID。
        """
        with self.lock:
            if self.is_playing_flag:
                self.stop()

        self.stop_event.clear()
        self.playback_thread = threading.Thread(
            target=self._playback_task,
            args=(sound_path, volume, loop_count, device_id)
        )
        self.playback_thread.daemon = True
        self.playback_thread.start()

    def _playback_task(self, sound_path, volume, loop_count, device_id):
        try:
            audio = AudioSegment.from_file(sound_path)

            # 应用音量调整
            if volume != 100:
                # 将 0-100 的线性音量转换为 dB
                # 0 -> -inf dB (静音), 100 -> 0 dB (原始音量)
                if volume == 0:
                    audio = audio - 100 # 大幅降低音量以模拟静音
                else:
                    gain = 20 * np.log10(volume / 100.0)
                    audio = audio + gain

            samples = np.array(audio.get_array_of_samples()).astype(np.float32)
            samples /= (2**(8 * audio.sample_width - 1))
            if audio.channels > 1:
                samples = samples.reshape((-1, audio.channels))

            with self.lock:
                self.is_playing_flag = True

            start_frame = 0
            current_loop = 1

            def callback(outdata, frames, time, status):
                nonlocal start_frame, current_loop
                if status:
                    print(status, file=sys.stderr)
                
                if self.stop_event.is_set():
                    outdata.fill(0)
                    raise sd.CallbackStop

                chunk_end = start_frame + frames
                remaining_frames = len(samples) - start_frame

                if remaining_frames < frames:
                    outdata[:remaining_frames] = samples[start_frame:]
                    outdata[remaining_frames:] = 0
                    
                    # 检查是否需要循环
                    if loop_count == -1: # 无限循环
                        start_frame = 0
                    elif current_loop < loop_count:
                        current_loop += 1
                        start_frame = 0
                    else:
                        raise sd.CallbackStop # 播放完成
                else:
                    outdata[:] = samples[start_frame:chunk_end]
                    start_frame = chunk_end

            with sd.OutputStream(
                samplerate=audio.frame_rate,
                device=device_id,
                channels=audio.channels,
                callback=callback
                # 移除 finished_callback，由 'with' 语句和 finally 子句处理清理
            ) as stream:
                with self.lock:
                    self.stream = stream
                # 等待直到流停止（无论是正常结束还是被外部调用 stop()）
                # stream.active 会在 callback 抛出 CallbackStop 或流被关闭后变为 False
                while stream.active and not self.stop_event.is_set():
                    sd.sleep(100) # 等待100毫秒，避免CPU空转

        except Exception as e:
            # CallbackStop 异常也会在这里被捕获，这是正常的流程
            if not isinstance(e, sd.CallbackStop):
                print(f"Error in playback thread: {e}")
        finally:
            with self.lock:
                # 确保流状态被清理
                self.stream = None
                self.is_playing_flag = False
            
            # 播放结束，发射信号
            self.playback_finished.emit()

    def stop(self):
        """停止当前播放的音频。"""
        if not self.stop_event.is_set():
            self.stop_event.set()
        
        # 立即返回，不阻塞UI线程
        # 音频流的关闭由 finished_callback 或回调中的异常处理来保证

    def is_playing(self):
        """检查是否正在播放。"""
        with self.lock:
            return self.is_playing_flag



def split_gif_to_frames(gif_path):
    # 打开GIF文件
    gif = Image.open(gif_path)
    frames = []
    try:
        while True:
            # 复制当前帧
            frame_img = gif.copy()
            frames.append(frame_img)
            # 尝试跳到下一帧， 如果没有帧，会抛出异常
            gif.seek(gif.tell() + 1)
            
    except EOFError:
        pass # 循环结束，说明已经到最后一帧
    except Exception as e:
        print(f"Error seeking GIF frames: {e}")
        return []  # 返回空列表，防止程序崩溃
    return frames

def split_mp4_to_frames(mp4_path):
    # 打开 MP4 文件
    try:
        clip = VideoFileClip(mp4_path)
        frames = []
        for frame in clip.iter_frames():
            # Convert numpy array frame to PIL Image
            frame_img = Image.fromarray(frame)
            
            # Append the PIL Image object to frames list
            frames.append(frame_img)
            
        clip.close() # 关闭资源
    except Exception as e:
         print(f"Error splitting mp4 to frames: {e}")
         return []
    return frames


# 获取屏幕物理分辨率
def get_real_screen_resolution() -> dict:
    # 在 Linux 下无法直接获取物理分辨率，这里采用一种近似方法，使用 PyQt 获取屏幕尺寸
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QtCore.QCoreApplication([])
    screen = app.desktop().screenGeometry()
    width = screen.width()
    height = screen.height()
    return {"width": width, "height": height}

def calculate_screen_scaling_ratio() -> float:
     # 获取屏幕宽度
    screen_size = get_real_screen_resolution()
    ratio = screen_size["width"] / 1920
    return ratio * 1.2

def set_pos(pos, object):
    for i in range(len(pos)):
        pos[i] = int(pos[i])
    object.setGeometry(QtCore.QRect(pos[0],
                                    pos[1],
                                    pos[2],
                                    pos[3]))


def get_output_devices():
    """获取所有可用的音频输出设备"""
    try:
        devices = sd.query_devices()
        output_devices = [device for device in devices if device['max_output_channels'] > 0]
        return output_devices
    except Exception as e:
        print(f"Error querying audio devices: {e}")
        return []


def play_sound(sound_path, device_id=None):
    """
    在指定的音频设备上播放声音。
    :param sound_path: 音频文件的路径。
    :param device_id: 要使用的输出设备的ID。如果为None，则使用默认设备。
    """
    try:
        # 使用pydub加载音频文件，它支持多种格式
        audio = AudioSegment.from_file(sound_path)
        
        # 将音频数据转换为numpy数组
        samples = np.array(audio.get_array_of_samples()).astype(np.float32)
        
        # 标准化到 [-1.0, 1.0]
        samples /= (2**(8 * audio.sample_width - 1))
        
        # 如果是立体声，需要重塑数组
        if audio.channels > 1:
            samples = samples.reshape((-1, audio.channels))

        # 播放
        sd.play(samples, samplerate=audio.frame_rate, device=device_id)
        sd.wait() # 等待播放完成

    except sd.PortAudioError as pae:
        print(f"!!! [PortAudioError] on device {device_id}: {pae}")
        print(f"!!! Host API: {pae.hostapi_error_info}")
    except Exception as e:
        import traceback
        print(f"!!! [Error] playing sound on device {device_id}: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    print(calculate_screen_scaling_ratio())
