import yaml
import os
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

def load_config(path: pathlib.Path):
    # 加载YAML文件
    path = str(path)
    if not os.path.isfile(path):
        print("error:你的config.yml不存在，请创建，并且这样初始化")
        print("imgs_dir : ")
        return 0
    else:
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
    ratio = calculate_screen_scaling_ratio()
    for i in range(len(pos)):
        pos[i] = int(pos[i] * ratio)
    object.setGeometry(QtCore.QRect(pos[0],
                                    pos[1],
                                    pos[2],
                                    pos[3]))

def get_absolute_dir(action="source_code"):
    # 从源码运行时，执行目录就是main.py所在目录
    if action == "source_code":
        absolute_dir = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
    # one-directory 打包后，运行目录在_internel下，∴需要向上一级
    # 打包时运行下方代码
    else:
        absolute_dir = pathlib.Path(os.path.dirname(os.path.abspath(__file__))).parent
    return absolute_dir

if __name__ == "__main__":
    print(calculate_screen_scaling_ratio())
