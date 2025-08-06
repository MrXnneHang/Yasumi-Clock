from PyQt5.QtWidgets import QDialog, QCheckBox, QSlider, QVBoxLayout, QLabel, QRadioButton, QButtonGroup, QGroupBox, QHBoxLayout, QSpinBox, QPushButton, QComboBox
from PyQt5.QtCore import Qt, pyqtSignal
from util import load_config, save_config, get_absolute_dir, get_output_devices

class SettingsWindow(QDialog):
    # 定义一个信号，用于在播放完成时通知UI线程
    test_sound_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(300, 350)  # 调整窗口大小

        self.absolute_dir = get_absolute_dir()
        self.config = load_config(
            self.absolute_dir / "yasumi_config.yml",
            self.absolute_dir / "user_config.yml"
        )

        self.initUI()
        self.load_settings()
        self.connect_signals()
        self.is_testing_sound = False

    def initUI(self):
        layout = QVBoxLayout()

        # 强制休息
        self.force_rest_checkbox = QCheckBox("启用强制休息 (工作时间结束后强制进入休息)", self)
        layout.addWidget(self.force_rest_checkbox)

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

        # 音频输出设备选择
        output_device_groupbox = QGroupBox("音频输出设备", self)
        output_device_layout = QVBoxLayout()
        self.output_device_combo = QComboBox(self)
        output_device_layout.addWidget(self.output_device_combo)
        output_device_groupbox.setLayout(output_device_layout)
        layout.addWidget(output_device_groupbox)

        self.populate_output_devices()

        # 测试按钮
        self.test_button = QPushButton("测试", self)
        layout.addWidget(self.test_button)

        self.setLayout(layout)

    def populate_output_devices(self):
        """填充音频输出设备下拉列表"""
        self.output_device_combo.clear()
        # 添加默认选项，我们用特殊值-1代表默认
        self.output_device_combo.addItem("默认设备", -1)
        
        try:
            devices = get_output_devices()
            for device in devices:
                # 显示设备名称，存储设备ID
                self.output_device_combo.addItem(f"{device['name']}", device['index'])
        except Exception as e:
            print(f"无法加载音频设备: {e}")
            # 可以添加一个禁用的项来提示错误
            self.output_device_combo.addItem("无法加载设备", -2)
            self.output_device_combo.model().item(self.output_device_combo.count() - 1).setEnabled(False)

    def connect_signals(self):
        # 连接信号到槽，实现即时保存
        self.force_rest_checkbox.stateChanged.connect(self.save_settings)
        self.notification_checkbox.stateChanged.connect(self.save_settings)
        self.volume_slider.valueChanged.connect(self.save_settings)
        self.mode_button_group.buttonClicked.connect(self.save_settings)
        self.loop_n_spinbox.valueChanged.connect(self.save_settings)
        self.output_device_combo.currentIndexChanged.connect(self.save_settings)
        self.test_button.clicked.connect(self.toggle_test_sound)
        self.test_sound_finished.connect(self.on_test_sound_finished)

    def load_settings(self):
        # 加载配置并设置控件
        yasumi_clock_config = self.config.get("yasumi_clock", {})
        notification_config = yasumi_clock_config.get("notification", {})

        force_rest_enabled = yasumi_clock_config.get("force_rest", False)
        self.force_rest_checkbox.setChecked(force_rest_enabled)
        
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

        # 加载音频输出设备
        # 我们现在保存的是设备ID，而不是一个字符串
        output_device_id = notification_config.get("output_device_id", -1) # -1 代表默认
        
        # 查找具有该ID的项并设置为当前项
        index_to_set = self.output_device_combo.findData(output_device_id)
        if index_to_set != -1:
            self.output_device_combo.setCurrentIndex(index_to_set)
        else:
            # 如果找不到保存的ID（比如设备被拔出），则恢复到默认
            self.output_device_combo.setCurrentIndex(0)

    def toggle_test_sound(self):
        """测试或停止提醒音"""
        if self.is_testing_sound:
            # 如果正在测试，则停止声音
            if self.parent() and hasattr(self.parent(), 'notification_player'):
                self.parent().notification_player.stop()
            self.test_button.setText("测试")
            self.is_testing_sound = False
        else:
            # 如果没有在测试，则开始播放
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
                
            # 从下拉框获取当前选择的设备ID
            selected_device_id = self.output_device_combo.currentData()
            
            # -1是我们为“默认设备”设置的特殊值
            if selected_device_id != -1:
                test_config["output_device_id"] = selected_device_id
            else:
                pass # 使用默认设备

            # 当播放完成时，SoundPlayer会调用这个函数，它会发射一个信号
            def on_finish_callback():
                self.test_sound_finished.emit()

            # 调用主窗口的播放函数，并传入回调
            if self.parent() and hasattr(self.parent(), 'play_notification_sound'):
                self.parent().play_notification_sound(
                    notification_config=test_config,
                    on_finish=on_finish_callback
                )
                self.test_button.setText("停止")
                self.is_testing_sound = True

    def on_test_sound_finished(self):
        """在主GUI线程中安全地更新UI"""
        self.test_button.setText("测试")
        self.is_testing_sound = False

    def save_settings(self):
        # 创建一个只包含用户设置的字典
        user_settings = {
            "yasumi_clock": {
                "force_rest": self.force_rest_checkbox.isChecked(),
                "notification": {
                    "enabled": self.notification_checkbox.isChecked(),
                    "volume": self.volume_slider.value(),
                    "loop_count": self.loop_n_spinbox.value(),
                    "output_device_id": self.output_device_combo.currentData()
                }
            }
        }

        # 根据单选按钮确定播放模式
        if self.radio_loop_play.isChecked():
            user_settings["yasumi_clock"]["notification"]["mode"] = "loop_play"
        elif self.radio_loop_n.isChecked():
            user_settings["yasumi_clock"]["notification"]["mode"] = "loop_n_times"
        else:
            user_settings["yasumi_clock"]["notification"]["mode"] = "play_once"
            
        # 只将用户设置保存到 user_config.yml
        save_config(user_settings, self.absolute_dir / "user_config.yml")

    def accept(self):
        # self.save_settings() # 不再需要在这里保存，因为设置是即时保存的
        super().accept()

    def reject(self):
        # 用户取消，不需要保存
        super().reject()

    def closeEvent(self, event):
        """窗口关闭事件，停止测试音"""
        if self.is_testing_sound:
            if self.parent() and hasattr(self.parent(), 'notification_player'):
                self.parent().notification_player.stop()
        super().closeEvent(event)
