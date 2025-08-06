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

def combine_path(abs_path:pathlib.Path,rel_path:str):
    # 合并多重路径
    rel_paths = rel_path.split("/")
    for path in rel_paths:
        abs_path = abs_path / path
    return str(abs_path)

def save_config(data, path: pathlib.Path):
    """保存配置到YAML文件"""
    path = str(path)
    with open(path, 'w', encoding='utf-8') as file:
        yaml.dump(data, file, allow_unicode=True, sort_keys=False)

def deep_merge_dicts(d1, d2):
    """
    深度合并两个字典。
    - 如果键在d2中也存在于d1中，并且值都是字典，则递归合并。
    - 否则，d2中的值将覆盖d1中的值。
    """
    for k, v in d2.items():
        if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
            d1[k] = deep_merge_dicts(d1[k], v)
        else:
            d1[k] = v
    return d1

def load_config(*paths: pathlib.Path):
    """加载并合并多个YAML文件。"""
    config = {}
    for path in paths:
        if path.is_file():
            with open(path, 'r', encoding='utf-8') as file:
                new_config = yaml.safe_load(file)
                if new_config:
                    config = deep_merge_dicts(config, new_config)
    
    if not config:
        raise FileNotFoundError(f"所有指定的配置文件都未找到或为空。")

    return config


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

def get_absolute_dir(): 
    """ 获取资源的绝对路径，兼容源码运行和PyInstaller打包 """
    # 检查是否被打包
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 如果是打包状态，基础路径是 sys._MEIPASS，即临时解压目录
        absolute_dir = pathlib.Path(sys._MEIPASS)
    else:
        # 如果是源码运行状态，基础路径是当前文件(__file__)所在的目录
        absolute_dir = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
    return absolute_dir

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
