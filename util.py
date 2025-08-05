import yaml
import os
import sys
import pathlib
from moviepy.editor import VideoFileClip
from PIL import Image
from PyQt5 import QtCore
import platform

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

def load_config(path: pathlib.Path):
    """加载YAML文件，如果文件不存在则抛出异常。"""
    if not path.is_file(): # 使用pathlib的方式检查文件
        # 抛出一个明确的错误，而不是返回一个神奇的数字
        raise FileNotFoundError(f"配置文件未找到或不是一个文件，路径: {path}")
    
    with open(path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    
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

if __name__ == "__main__":
    print(calculate_screen_scaling_ratio())
