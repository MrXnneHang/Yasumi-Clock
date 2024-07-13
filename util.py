import yaml
import os


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