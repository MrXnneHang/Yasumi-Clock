import yaml
import os
from moviepy.editor import VideoFileClip
from PyQt5 import QtCore



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