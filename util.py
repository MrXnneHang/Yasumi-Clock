import yaml
import os
from moviepy.editor import VideoFileClip
from PyQt5 import QtCore
import matplotlib.pyplot as plt 



def load_config(path="./config.yml"):

    # 加载YAML文件
    if not os.path.isfile(path):
        print(f"error:你的{path}不存在，请创建，并且这样初始化")
        # print("imgs_dir : ")
        return 0
    else:
        with open(path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        
        return config



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

def set_pos(pos,object):
    for i in range(len(pos)):
        pos[i] = int(pos[i])
    object.setGeometry(QtCore.QRect(pos[0],
                                    pos[1],
                                    pos[2],
                                    pos[3]))

def date_scrollation(date):
    """滚动时间month-day,每次往回滚动一天，遵守大小月，闰年，平年，月末
       比如输入是2022-02-01，输出是2022-01-31"""
    year,month,day = date.split("-")
    year = int(year)
    month = int(month)
    day = int(day)
    if month == 1:
        if day == 1:
            year -= 1
            month = 12
            day = 31
        else:
            day -= 1
    elif month == 2:
        if day == 1:
            month -= 1
            if year % 4 == 0:
                day = 29
            else:
                day = 28
        else:
            day -= 1
    elif month == 3:
        if day == 1:
            month -= 1
            day = 28
        else:
            day -= 1
    elif month == 4:
        if day == 1:
            month -= 1
            day = 31
        else:
            day -= 1
    elif month == 5:
        if day == 1:
            month -= 1
            day = 30
        else:
            day -= 1
    elif month == 6:
        if day == 1:
            month -= 1
            day = 31
        else:
            day -= 1
    elif month == 7:
        if day == 1:
            month -= 1
            day = 30
        else:
            day -= 1
    elif month == 8:
        if day == 1:
            month -= 1
            day = 31
        else:
            day -= 1
    elif month == 9:
        if day == 1:
            month -= 1
            day = 31
        else:
            day -= 1
    elif month == 10:
        if day == 1:
            month -= 1
            day = 30
        else:
            day -= 1
    elif month == 11:
        if day == 1:
            month -= 1
            day = 31
        else:
            day -= 1
    elif month == 12:
        if day == 1:
            month -= 1
            day = 30
        else:
            day -= 1
    return f"{year}-{month}-{day}"