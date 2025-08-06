from PyQt5.QtWidgets import QDialog, QCheckBox, QSlider, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from util import load_config, save_config, get_absolute_dir

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(300, 150)

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

        # 音量控制
        volume_layout = QVBoxLayout()
        volume_label = QLabel("音量", self)
        self.volume_slider = QSlider(Qt.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        layout.addLayout(volume_layout)

        self.setLayout(layout)

    def connect_signals(self):
        # 连接信号到槽，实现即时保存
        self.notification_checkbox.stateChanged.connect(self.save_settings)
        self.volume_slider.valueChanged.connect(self.save_settings)

    def load_settings(self):
        # 加载配置并设置控件
        notification_enabled = self.config.get("yasumi_clock", {}).get("notification", {}).get("enabled", True)
        self.notification_checkbox.setChecked(notification_enabled)

        volume = self.config.get("yasumi_clock", {}).get("notification", {}).get("volume", 80)
        self.volume_slider.setValue(volume)

    def save_settings(self):
        # 保存配置
        self.config["yasumi_clock"]["notification"]["enabled"] = self.notification_checkbox.isChecked()
        self.config["yasumi_clock"]["notification"]["volume"] = self.volume_slider.value()
        save_config(self.config, self.absolute_dir / "yasumi_config.yml")

    def accept(self):
        # self.save_settings() # 不再需要在这里保存，因为设置是即时保存的
        super().accept()

    def reject(self):
        # 用户取消，不需要保存
        super().reject()
