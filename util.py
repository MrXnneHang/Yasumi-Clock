import imageio
import yaml
import os
import numpy as np
from moviepy.editor import VideoFileClip
from win32.lib import win32con
from win32 import win32gui,win32print
from PyQt5 import QtCore

def load_config(path="./config.yml"):

    # 加载YAML文件
    if not os.path.isfile(path):
        print("error:你的config.yml不存在，请创建，并且这样初始化")
        print("imgs_dir : ")
        return 0
    else:
        with open(path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        
        return config

# 留左去右。
def crop_gif(gif_path, output_path, target_ratio=7/6):
    # Load the GIF using imageio to preserve animation
    gif = imageio.mimread(gif_path, memtest=False)
    # Get original dimensions
    original_height, original_width, _ = gif[0].shape  # assuming all frames are the same size
    # Calculate target width to maintain aspect ratio
    target_width = int(original_height * target_ratio)
    # Calculate how much to crop from the right side
    crop_width = original_width - target_width
    # Define the region to keep (left, upper, right, lower)
    keep_region = (0, 0, original_width - crop_width, original_height)
    # Crop each frame
    cropped_frames = [frame[:, :original_width - crop_width, :] for frame in gif]
    # Save the cropped frames as a new GIF
    imageio.mimsave(output_path, cropped_frames)

from PIL import Image

def split_gif_to_frames(gif_path):
    # Open the GIF file
    gif = Image.open(gif_path)

    frames = []
    try:
        while True:
            # Try to seek to the next frame
            gif.seek(gif.tell() + 1)

            # Copy the current frame into a new PIL Image object
            frame_img = gif.copy()

            # Append the PIL Image object to frames list
            frames.append(frame_img)

    except EOFError:
        pass

    return frames


def split_mp4_to_frames(mp4_path):
    # Open the MP4 file
    clip = VideoFileClip(mp4_path)

    frames = []
    for frame in clip.iter_frames():
        # Convert numpy array frame to PIL Image
        frame_img = Image.fromarray(frame)
        
        # Append the PIL Image object to frames list
        frames.append(frame_img)

    return frames


# 获取屏幕物理分辨率
def get_real_screen_resolution()->dict:
    hDC = win32gui.GetDC (0)
    width = win32print.GetDeviceCaps (hDC,win32con.DESKTOPHORZRES)
    height = win32print.GetDeviceCaps (hDC,win32con.DESKTOPVERTRES)
    return {"width":width,"height":height}


def calculate_screen_scaling_ratio()->float:
    screen_size = get_real_screen_resolution()
    ratio = screen_size["width"] / 1920
    return ratio

def set_pos(pos,object):
    ratio = calculate_screen_scaling_ratio()
    for i in range(len(pos)):
        pos[i] = int(pos[i] * ratio)
    object.setGeometry(QtCore.QRect(pos[0],
                                    pos[1],
                                    pos[2],
                                    pos[3]))
        

if __name__ == "__main__":
    print(calculate_screen_scaling_ratio())