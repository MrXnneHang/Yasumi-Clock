import yaml
import os
import sys
import pathlib
from moviepy.editor import VideoFileClip
from PIL import Image
from PyQt5 import QtCore
from PyQt5.QtCore import Qt
import platform
import sounddevice as sd
import numpy as np
from pydub import AudioSegment

import threading
import logging
import logging.handlers
import traceback

if platform.system() == "Windows":
    import winreg

# macOS特定导入：用于设置窗口在全屏应用上方显示
if platform.system() == "Darwin":
    try:
        import objc
        from ctypes import c_void_p
        HAS_OBJC = True
    except ImportError:
        HAS_OBJC = False
        logging.warning("pyobjc not available, some macOS window features may not work")

# --- StreamToLogger for stderr redirection ---
class StreamToLogger:
    """
    A class to redirect stream output (like stderr) to a logger.
    """
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass

# --- Exception Hook ---
def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Custom exception hook to log unhandled exceptions.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

# --- App Data Directory ---
def get_app_data_dir():
    """获取用于存储应用程序数据的持久化目录，并确保它存在。"""
    # 检查是否是源码运行
    is_source_run = not (getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'))
    
    if is_source_run:
        # 如果是源码运行，使用项目根目录下的 .dev_user_data 文件夹
        path = pathlib.Path().cwd() / ".dev_user_data"
        logging.info("Running from source, using development user data directory: %s", path)
    else:
        # 如果是打包后运行，使用标准的系统路径
        system = platform.system()
        if system == "Windows":
            path = pathlib.Path(os.getenv('APPDATA')) / "YasumiClock"
        elif system == "Darwin":  # macOS
            path = pathlib.Path.home() / "Library" / "Application Support" / "YasumiClock"
        else:  # Linux
            path = pathlib.Path.home() / ".config" / "YasumiClock"
    
    # 确保目录存在
    path.mkdir(parents=True, exist_ok=True)
    return path

# --- Logging Setup ---
def setup_logger():
    """配置全局日志记录器，将日志写入到应用程序数据目录中。"""
    log_dir = get_app_data_dir()
    log_file = log_dir / "yasumi.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 避免重复添加 handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # 创建一个文件 handler，按天轮换日志
    # 保留最近7天的日志
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=7, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)

    # 创建一个控制台 handler (用于调试)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)

    # 定义日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    # 添加 handlers 到 logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    logging.info("Logger has been configured. Logging to %s", log_file)

    # --- Redirect stderr and set excepthook ---
    # 1. Set the custom exception hook for unhandled exceptions
    sys.excepthook = handle_exception

    # 2. Redirect stderr to the logger
    stderr_logger = logging.getLogger('STDERR')
    sys.stderr = StreamToLogger(stderr_logger, logging.ERROR)
    logging.info("Stderr has been redirected to the logger.")


# --- Startup Management (Windows Only) ---
def get_executable_path():
    """获取可执行文件的路径，兼容源码和打包后的exe"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe
        return sys.executable
    else:
        # 如果是源码运行
        return os.path.abspath(sys.argv[0])

def _set_startup_windows(app_name, enable=True):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    executable_path = get_executable_path()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            if enable:
                # 添加 --autostart 参数
                command = f'"{executable_path}" --autostart'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
                logging.info(f"已将 '{app_name}' 添加到 Windows 开机自启。")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    logging.info(f"已将 '{app_name}' 从 Windows 开机自启中移除。")
                except FileNotFoundError:
                    pass # Already removed
    except Exception as e:
        logging.error(f"操作 Windows 注册表失败: {e}")

def _get_startup_windows(app_name):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, app_name)
            # 检查值中是否包含 --autostart 参数
            return "--autostart" in value
    except FileNotFoundError:
        return False
    except Exception:
        return False

def _get_launch_agent_path(app_name):
    return pathlib.Path.home() / "Library" / "LaunchAgents" / f"com.{app_name.lower().replace(' ', '')}.plist"

def _set_startup_macos(app_name, enable=True):
    plist_path = _get_launch_agent_path(app_name)
    executable_path = get_executable_path()
    if enable:
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{app_name.lower().replace(' ', '')}</string>
    <key>ProgramArguments</key>
    <array><string>{executable_path}</string><string>--autostart</string></array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
        try:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            plist_path.write_text(plist_content)
            logging.info(f"已为 '{app_name}' 创建 macOS 登录项。")
        except Exception as e:
            logging.error(f"创建 macOS 登录项失败: {e}")
    else:
        if plist_path.exists():
            try:
                plist_path.unlink()
                logging.info(f"已为 '{app_name}' 移除 macOS 登录项。")
            except Exception as e:
                logging.error(f"移除 macOS 登录项失败: {e}")

def _get_startup_macos(app_name):
    return _get_launch_agent_path(app_name).exists()

def _get_autostart_path(app_name):
    return pathlib.Path.home() / ".config" / "autostart" / f"{app_name.lower().replace(' ', '-')}.desktop"

def _set_startup_linux(app_name, enable=True):
    desktop_file_path = _get_autostart_path(app_name)
    executable_path = get_executable_path()
    if enable:
        desktop_entry = f"""[Desktop Entry]
Type=Application
Name={app_name}
Exec="{executable_path}" --autostart
Comment=Start {app_name} on login
X-GNOME-Autostart-enabled=true"""
        try:
            desktop_file_path.parent.mkdir(parents=True, exist_ok=True)
            desktop_file_path.write_text(desktop_entry)
            logging.info(f"已为 '{app_name}' 创建 Linux 自启动项。")
        except Exception as e:
            logging.error(f"创建 Linux 自启动项失败: {e}")
    else:
        if desktop_file_path.exists():
            try:
                desktop_file_path.unlink()
                logging.info(f"已为 '{app_name}' 移除 Linux 自启动项。")
            except Exception as e:
                logging.error(f"移除 Linux 自启动项失败: {e}")

def _get_startup_linux(app_name):
    return _get_autostart_path(app_name).exists()

def set_startup_status(app_name, enable=True):
    """在当前操作系统中设置或移除开机自启项。"""
    system = platform.system()
    if system == "Windows":
        _set_startup_windows(app_name, enable)
    elif system == "Darwin":
        _set_startup_macos(app_name, enable)
    elif system == "Linux":
        _set_startup_linux(app_name, enable)
    else:
        logging.warning(f"当前操作系统 ({system}) 不支持设置开机自启。")

def get_startup_status(app_name):
    """检查应用是否已在当前操作系统中设置为开机自启。"""
    system = platform.system()
    if system == "Windows":
        return _get_startup_windows(app_name)
    elif system == "Darwin":
        return _get_startup_macos(app_name)
    elif system == "Linux":
        return _get_startup_linux(app_name)
    return False

# --- Start of new ConfigManager ---
class ConfigManager:
    """
    统一管理应用程序的配置。
    加载、合并和提供对 yasumi_config.yml, user_config.yml 和 src.yml 的访问。
    处理资源路径解析和用户配置的保存。
    """
    def __init__(self):
        self.bundle_dir = self._get_bundle_dir()
        self.user_data_dir = self._get_user_data_dir()
        self.config = {}
        self.src_config = {}
        self._load_all_configs()

    def _get_bundle_dir(self):
        """ 获取资源的绝对路径（捆绑包或脚本目录），兼容源码运行和PyInstaller打包 """
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return pathlib.Path(sys._MEIPASS)
        else:
            return pathlib.Path(__file__).parent.resolve()

    def _get_user_data_dir(self):
        """获取用于存储用户数据的持久化目录，并确保它存在。该方法与顶层函数 get_app_data_dir 保持一致。"""
        return get_app_data_dir()

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
        default_config_path = self.bundle_dir / "yasumi_config.yml"
        user_config_path = self.user_data_dir / "user_config.yml" # 使用持久化目录
        src_config_path = self.bundle_dir / "src.yml"

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
        current_path = self.bundle_dir
        rel_paths = rel_path.split("/")
        for path_part in rel_paths:
            current_path = current_path / path_part
        return str(current_path)

    def save_user_config(self, data: dict):
        """将用户特定配置保存到 user_config.yml"""
        user_config_path = self.user_data_dir / "user_config.yml" # 使用持久化目录
        with open(user_config_path, 'w', encoding='utf-8') as file:
            yaml.dump(data, file, allow_unicode=True, sort_keys=False)
        
        # 保存后立即重新加载配置，以确保内存中的配置是最新的
        self._load_all_configs()

    def save_session_state(self, state: dict | None):
        """
        保存完整的番茄钟会话状态到用户配置文件。
        如果 state 为 None, 则表示清除已保存的状态。
        """
        from datetime import datetime
        
        user_config_path = self.user_data_dir / "user_config.yml"
        current_user_config = {}
        if user_config_path.is_file():
            with open(user_config_path, 'r', encoding='utf-8') as file:
                current_user_config = yaml.safe_load(file) or {}
        
        # 确保 yasumi_clock 键存在
        if 'yasumi_clock' not in current_user_config:
            current_user_config['yasumi_clock'] = {}

        if state:
            # 添加时间戳并保存状态
            state['timestamp'] = datetime.now().isoformat()
            current_user_config['yasumi_clock']['session_state'] = state
        elif 'session_state' in current_user_config.get('yasumi_clock', {}):
            # 如果 state 为 None 且存在旧状态，则移除
            del current_user_config['yasumi_clock']['session_state']

        with open(user_config_path, 'w', encoding='utf-8') as file:
            yaml.dump(current_user_config, file, allow_unicode=True, sort_keys=False)
        
        # 立即重新加载，确保内存同步
        self._load_all_configs()

    def load_session_state(self) -> dict | None:
        """
        从用户配置文件加载完整的番茄钟会话状态。
        如果状态已过期或无效，则返回 None。
        """
        from datetime import datetime, timedelta

        session_state = self.config.get('yasumi_clock', {}).get('session_state')
        
        if not session_state or 'timestamp' not in session_state or 'state_name' not in session_state:
            return None

        try:
            saved_time = datetime.fromisoformat(session_state['timestamp'])
            # 如果状态是1小时前保存的，就认为它已过期
            if datetime.now() - saved_time > timedelta(hours=1):
                logging.info("Loaded session state is older than 1 hour, ignoring.")
                self.save_session_state(None) # 清除过时状态
                return None
            
            # 返回经过时间（秒）
            session_state['elapsed_seconds_since_save'] = (datetime.now() - saved_time).total_seconds()
            return session_state

        except (ValueError, TypeError):
            logging.error("Error parsing session state timestamp.", exc_info=True)
            self.save_session_state(None) # 清除无效状态
            return None

    def save_daily_pomodoro_count(self, count: int):
        """保存番茄钟每日计数（以凌晨5点为界）到用户配置文件。"""
        from datetime import datetime, date, timedelta
        
        now = datetime.now()
        logical_today = now.date() if now.hour >= 5 else now.date() - timedelta(days=1)
        
        state_data = {
            'yasumi_clock': {
                'daily_pomodoro_state': {
                    'date': logical_today.isoformat(),
                    'count': count
                }
            }
        }
        
        user_config_path = self.user_data_dir / "user_config.yml"
        current_user_config = {}
        if user_config_path.is_file():
            with open(user_config_path, 'r', encoding='utf-8') as file:
                current_user_config = yaml.safe_load(file) or {}
        
        merged_config = self._deep_merge_dicts(current_user_config, state_data)
        
        with open(user_config_path, 'w', encoding='utf-8') as file:
            yaml.dump(merged_config, file, allow_unicode=True, sort_keys=False)
        
        self._load_all_configs()

    def load_daily_pomodoro_count(self) -> int:
        """从用户配置文件加载番茄钟每日计数，如果不是“今天”（以凌晨5点为界），则重置。"""
        from datetime import datetime, date, timedelta
        
        now = datetime.now()
        state_data = self.config.get('yasumi_clock', {}).get('daily_pomodoro_state', {})
        saved_date_str = state_data.get('date')
        
        if not saved_date_str:
            return 0
            
        logical_today = now.date() if now.hour >= 5 else now.date() - timedelta(days=1)
        
        try:
            saved_date = date.fromisoformat(saved_date_str)
        except (ValueError, TypeError):
            return 0

        if saved_date == logical_today:
            return state_data.get('count', 0)
        
        return 0

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
                    logging.warning(f"Sound device status: {status}")
                
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
                logging.error(f"Error in playback thread: {e}", exc_info=True)
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
        logging.error(f"Error seeking GIF frames: {e}", exc_info=True)
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
         logging.error(f"Error splitting mp4 to frames: {e}", exc_info=True)
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
        logging.error(f"Error querying audio devices: {e}", exc_info=True)
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
        logging.error(f"!!! [PortAudioError] on device {device_id}: {pae}")
        logging.error(f"!!! Host API: {pae.hostapi_error_info}")
    except Exception as e:
        import traceback
        logging.exception(f"!!! [Error] playing sound on device {device_id}: {e}")


def show_window_on_top(window):
    """
    确保窗口正确显示在最前面并获得焦点（macOS兼容性修复）。

    在macOS上，当主窗口最小化时，仅调用show()不足以让新窗口显示在最前面。
    此函数通过组合调用showNormal()、raise_()和activateWindow()来解决这个问题。
    同时设置WA_MacAlwaysShowToolWindow属性，防止工具窗口在应用失焦时消失。
    并设置NSWindowCollectionBehavior，使窗口能够显示在全屏应用上方。

    :param window: 要显示的QWidget或QDialog对象
    """
    # macOS兼容性：防止工具窗口在应用失焦或切换工作区时消失
    window.setAttribute(Qt.WA_MacAlwaysShowToolWindow)

    # macOS兼容性：设置窗口在全屏应用上方显示
    if platform.system() == "Darwin" and HAS_OBJC:
        try:
            # 获取原生NSWindow对象
            nsview = objc.objc_object(c_void_p=window.winId().__int__())
            nswindow = nsview.window()

            # 关键步骤1：设置 NSPanel 的 styleMask 为 nonactivatingPanel
            # 这是让窗口能够在全屏应用上方显示的关键！
            # NSNonactivatingPanelMask = 128 (1 << 7)
            NSNonactivatingPanelMask = 1 << 7  # 128

            # 获取当前的 styleMask 并添加 NSNonactivatingPanelMask
            current_style_mask = nswindow.styleMask()
            new_style_mask = current_style_mask | NSNonactivatingPanelMask
            nswindow.setStyleMask_(new_style_mask)

            # 关键步骤2：设置NSWindowCollectionBehavior标志
            # CanJoinAllSpaces: 窗口可以出现在所有空间（包括全屏应用的独立空间）
            # FullScreenAuxiliary: 窗口可以显示在全屏应用上方
            NSWindowCollectionBehaviorCanJoinAllSpaces = 1 << 0  # 1
            NSWindowCollectionBehaviorFullScreenAuxiliary = 1 << 8  # 256

            behavior = (NSWindowCollectionBehaviorCanJoinAllSpaces |
                       NSWindowCollectionBehaviorFullScreenAuxiliary)

            nswindow.setCollectionBehavior_(behavior)

            # 关键步骤3：设置窗口级别为主菜单级别
            NSMainMenuWindowLevel = 24
            nswindow.setLevel_(NSMainMenuWindowLevel)

        except Exception as e:
            logging.warning(f"Failed to set NSWindowCollectionBehavior: {e}")

    window.showNormal()
    window.raise_()
    window.activateWindow()


if __name__ == "__main__":
    logging.info(calculate_screen_scaling_ratio())
