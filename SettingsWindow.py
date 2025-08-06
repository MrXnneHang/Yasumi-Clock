from PyQt5.QtWidgets import QDialog, QCheckBox, QSlider, QVBoxLayout, QLabel, QRadioButton, QButtonGroup, QGroupBox, QHBoxLayout, QSpinBox, QPushButton
from PyQt5.QtCore import Qt
from util import load_config, save_config, get_absolute_dir

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(300, 280)  # 调整窗口大小

        self.absolute_dir = get_absolute_dir()
        self.config = load_config(self.absolute_dir / "yasumi_config.yml")

        self.initUI()
        self.load_settings()
        self.connect_signals()

    def initUI(self):
        layout = QVBoxLayout()

        # 休息结束提醒
        self.notification_checkbox = QCheckBox("启用休息结束提醒", self)
        layout.addWidget(self.notification_checkbox)

        # 提醒模式
        mode_groupbox = QGroupBox("提醒模式", self)
        mode_v_layout = QVBoxLayout() # 使用垂直布局

        self.radio_play_once = QRadioButton("播放一次", self)
        self.radio_loop_play = QRadioButton("循环播放 (无限)", self)
        
        # 循环 N 次的布局
        loop_n_layout = QHBoxLayout()
        self.radio_loop_n = QRadioButton("循环播放", self)
        self.loop_n_spinbox = QSpinBox(self)
        self.loop_n_spinbox.setRange(1, 99)
        self.loop_n_spinbox.setSuffix(" 次")
        loop_n_layout.addWidget(self.radio_loop_n)
        loop_n_layout.addWidget(self.loop_n_spinbox)
        
        mode_v_layout.addWidget(self.radio_play_once)
        mode_v_layout.addWidget(self.radio_loop_play)
        mode_v_layout.addLayout(loop_n_layout)
        
        mode_groupbox.setLayout(mode_v_layout)
        layout.addWidget(mode_groupbox)

        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.addButton(self.radio_play_once, 1)
        self.mode_button_group.addButton(self.radio_loop_play, 2)
        self.mode_button_group.addButton(self.radio_loop_n, 3)

        # 音量控制
        volume_layout = QVBoxLayout()
        volume_label = QLabel("音量", self)
        self.volume_slider = QSlider(Qt.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        layout.addLayout(volume_layout)

        # 测试按钮
        self.test_button = QPushButton("测试", self)
        layout.addWidget(self.test_button)

        self.setLayout(layout)

    def connect_signals(self):
        # 连接信号到槽，实现即时保存
        self.notification_checkbox.stateChanged.connect(self.save_settings)
        self.volume_slider.valueChanged.connect(self.save_settings)
        self.mode_button_group.buttonClicked.connect(self.save_settings)
        self.loop_n_spinbox.valueChanged.connect(self.save_settings)
        self.test_button.clicked.connect(self.test_sound)

    def load_settings(self):
        # 加载配置并设置控件
        notification_config = self.config.get("yasumi_clock", {}).get("notification", {})
        
        notification_enabled = notification_config.get("enabled", True)
        self.notification_checkbox.setChecked(notification_enabled)

        volume = notification_config.get("volume", 80)
        self.volume_slider.setValue(volume)

        mode = notification_config.get("mode", "play_once")
        loop_count = notification_config.get("loop_count", 3)
        self.loop_n_spinbox.setValue(loop_count)

        if mode == "loop_play":
            self.radio_loop_play.setChecked(True)
        elif mode == "loop_n_times":
            self.radio_loop_n.setChecked(True)
        else: # play_once
            self.radio_play_once.setChecked(True)

    def test_sound(self):
        """使用当前UI设置测试提醒音"""
        # 停止当前可能在播放的任何提醒音，以防用户连续点击
        if self.parent() and hasattr(self.parent(), 'notification_player'):
            self.parent().notification_player.stop()

        # 从UI控件直接构建一个临时的通知配置字典
        test_config = {
            "enabled": True,  # 测试时总是启用
            "volume": self.volume_slider.value(),
            "loop_count": self.loop_n_spinbox.value()
        }

        # 根据单选按钮确定播放模式
        if self.radio_loop_play.isChecked():
            test_config["mode"] = "loop_play"
        elif self.radio_loop_n.isChecked():
            test_config["mode"] = "loop_n_times"
        else:
            test_config["mode"] = "play_once"

        # 调用主窗口的播放函数，并传入临时配置
        # 我们假设父窗口（主窗口）有 play_notification_sound 方法
        if self.parent() and hasattr(self.parent(), 'play_notification_sound'):
            self.parent().play_notification_sound(notification_config=test_config)

    def save_settings(self):
        # 保存配置
        if "notification" not in self.config["yasumi_clock"]:
            self.config["yasumi_clock"]["notification"] = {}
            
        self.config["yasumi_clock"]["notification"]["enabled"] = self.notification_checkbox.isChecked()
        self.config["yasumi_clock"]["notification"]["volume"] = self.volume_slider.value()
        self.config["yasumi_clock"]["notification"]["loop_count"] = self.loop_n_spinbox.value()
        
        if self.radio_loop_play.isChecked():
            self.config["yasumi_clock"]["notification"]["mode"] = "loop_play"
        elif self.radio_loop_n.isChecked():
            self.config["yasumi_clock"]["notification"]["mode"] = "loop_n_times"
        else:
            self.config["yasumi_clock"]["notification"]["mode"] = "play_once"
            
        save_config(self.config, self.absolute_dir / "yasumi_config.yml")

    def accept(self):
        # self.save_settings() # 不再需要在这里保存，因为设置是即时保存的
        super().accept()

    def reject(self):
        # 用户取消，不需要保存
        super().reject()
