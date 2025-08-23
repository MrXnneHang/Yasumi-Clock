from PyQt5.QtWidgets import (QDialog, QCheckBox, QSlider, QVBoxLayout, QLabel,
                             QRadioButton, QButtonGroup, QGroupBox, QHBoxLayout,
                             QSpinBox, QPushButton, QComboBox, QFormLayout,
                             QListWidget, QStackedWidget, QWidget, QFrame, QToolButton)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
import os
import platform
import subprocess
from util import get_output_devices, SoundPlayer, ConfigManager, set_startup_status, get_startup_status
from mode_enums import OperatingMode
from FloatingWindow import FloatingWindow

class SettingsWindow(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(500, 400)

        if not parent or not hasattr(parent, 'config_manager'):
            raise ValueError("SettingsWindow must be initialized with a parent that has a 'config_manager' attribute.")
        
        self.config_manager = parent.config_manager
        self.config = self.config_manager.get_config()
        self.yasumi_clock_config = self.config.get("yasumi_clock", {})
        
        # 从 custom preset 中获取帮助文本
        self.help_texts = self.yasumi_clock_config.get("presets", {}).get("custom", {}).get("help_texts", {})
        
        self.staged_settings = {
            "active_mode_key": parent.engine.active_mode.value,
            "advanced_mode_enabled": self.yasumi_clock_config.get("advanced_mode_enabled", False)
        }

        self.sound_player = SoundPlayer()
        self.is_testing_sound = False
        
        self.initUI()
        self.load_settings()
        self.connect_signals()
 
    def initUI(self):
        main_layout = QHBoxLayout(self)

        self.nav_list = QListWidget(self)
        self.nav_list.addItems(["模式与循环", "通知提醒", "通用设置"])
        self.nav_list.setFixedWidth(120)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.create_mode_and_cycle_page())
        self.stack.addWidget(self.create_notification_page())
        self.stack.addWidget(self.create_general_page())

        button_layout = QVBoxLayout()
        self.save_button = QPushButton("保存并关闭")
        self.cancel_button = QPushButton("取消")
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)

        main_layout.addWidget(self.nav_list)
        main_layout.addWidget(self.stack, 1)
        main_layout.addLayout(button_layout)

    def create_mode_and_cycle_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # --- Advanced Mode Toggle ---
        self.advanced_mode_checkbox = QCheckBox("启用高级模式 (预设与自定义循环)")
        self.advanced_mode_checkbox.setToolTip("启用后可以选择不同的预设模式或自定义循环参数。\n禁用后将恢复为经典的手动调时模式。")
        layout.addWidget(self.advanced_mode_checkbox)

        # --- Mode Selection ---
        # --- Mode Selection & Description ---
        mode_selection_layout = QHBoxLayout()

        self.mode_groupbox = QGroupBox("高级模式设置")
        self.mode_button_group = QButtonGroup(self)
        self.radio_button_to_mode_key_map = {} # Changed from mode_map to key_map
        mode_layout = QVBoxLayout()

        presets = self.yasumi_clock_config.get("presets", {})
        # 确保 'custom' 模式总是在最前面
        preset_keys = sorted(presets.keys(), key=lambda x: (x != 'custom', x))

        for mode_key in preset_keys:
            mode_config = presets[mode_key]
            display_name = mode_config.get("name", mode_key)
            rb = QRadioButton(display_name)
            
            if mode_key == 'custom':
                self.custom_rb = rb # 保留对自定义rb的引用

            mode_layout.addWidget(rb)
            self.mode_button_group.addButton(rb)
            self.radio_button_to_mode_key_map[rb] = mode_key
        
        self.mode_groupbox.setLayout(mode_layout)
        # 将左侧的模式选择区域顶部对齐，防止其因右侧内容变化而上下移动
        mode_selection_layout.addWidget(self.mode_groupbox, 0, Qt.AlignTop)

        # --- Mode Description Area ---
        self.mode_description_label = QLabel("请选择一个模式以查看其详细说明。")
        self.mode_description_label.setWordWrap(True)
        self.mode_description_label.setAlignment(Qt.AlignTop)
        self.mode_description_label.setFrameShape(QFrame.StyledPanel)
        self.mode_description_label.setMinimumWidth(200)
        mode_selection_layout.addWidget(self.mode_description_label, 1) # Give it more space

        layout.addLayout(mode_selection_layout)

        # --- Custom Cycle Settings ---
        self.custom_cycle_groupbox = QGroupBox("自定义循环设置")
        self.custom_cycle_groupbox.setToolTip("这些设置仅在选择“自定义模式”时生效。")
        custom_cycle_layout = QVBoxLayout()
        custom_cycle_layout.setSpacing(0) # 让控件之间更紧凑
        custom_cycle_layout.setContentsMargins(10, 5, 10, 5)

        # --- Helper function for creating setting items ---
        def create_setting_widget(label_text, spinbox, description_text):
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            label = QLabel(label_text)
            
            help_button = QToolButton()
            help_button.setText("?")
            help_button.setFixedSize(18, 18)
            help_button.setCursor(Qt.PointingHandCursor)
            help_button.setStyleSheet("""
                QToolButton {
                    border: 1px solid #aaa;
                    border-radius: 9px;
                    font-weight: bold;
                    background-color: #f0f0f0;
                    color: #555;
                }
                QToolButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            
            help_button.clicked.connect(lambda: self.show_help_text(description_text))

            layout.addWidget(label)
            layout.addWidget(help_button)
            layout.addStretch()
            layout.addWidget(spinbox)
            
            return widget

        # --- Work Duration ---
        self.work_mins_spinbox = QSpinBox(self)
        self.work_mins_spinbox.setRange(1, 120)
        work_desc = self.help_texts.get("work_duration", "未找到帮助文本。")
        custom_cycle_layout.addWidget(create_setting_widget("工作时长 (分钟):", self.work_mins_spinbox, work_desc))

        # --- Short Break ---
        self.short_break_spinbox = QSpinBox(self)
        self.short_break_spinbox.setRange(1, 60)
        short_break_desc = self.help_texts.get("short_break", "未找到帮助文本。")
        custom_cycle_layout.addWidget(create_setting_widget("短休息时长 (分钟):", self.short_break_spinbox, short_break_desc))

        # --- Long Break ---
        self.long_break_spinbox = QSpinBox(self)
        self.long_break_spinbox.setRange(1, 120)
        long_break_desc = self.help_texts.get("long_break", "未找到帮助文本。")
        custom_cycle_layout.addWidget(create_setting_widget("长休息时长 (分钟):", self.long_break_spinbox, long_break_desc))

        # --- Cycles before Long Break ---
        self.cycles_spinbox = QSpinBox(self)
        self.cycles_spinbox.setRange(1, 10)
        cycles_desc = self.help_texts.get("cycles_before_long_break", "未找到帮助文本。")
        custom_cycle_layout.addWidget(create_setting_widget("长休息间隔 (循环次数):", self.cycles_spinbox, cycles_desc))
        
        custom_cycle_layout.addStretch()
        self.custom_cycle_groupbox.setLayout(custom_cycle_layout)
        layout.addWidget(self.custom_cycle_groupbox)
        
        layout.addStretch()
        return page

    def create_notification_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        # --- Idle Reminder Settings ---
        idle_reminder_group = QGroupBox("长时间未开始计时提醒")
        idle_reminder_layout = QVBoxLayout()

        self.idle_reminder_enabled_checkbox = QCheckBox("启用此功能")
        self.idle_reminder_enabled_checkbox.setToolTip("当一个番茄钟或休息结束后，如果长时间未开始下一个，则发出提醒。")
        idle_reminder_layout.addWidget(self.idle_reminder_enabled_checkbox)

        # Threshold setting
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("提醒阈值 (分钟):"))
        self.idle_threshold_spinbox = QSpinBox(self)
        self.idle_threshold_spinbox.setRange(1, 60)
        self.idle_threshold_spinbox.setToolTip("设置多长时间不活动后触发提醒。")
        threshold_layout.addWidget(self.idle_threshold_spinbox)
        threshold_layout.addStretch()
        idle_reminder_layout.addLayout(threshold_layout)

        # Alert type toggles
        self.idle_visual_alert_checkbox = QCheckBox("屏幕提醒")
        self.idle_sound_alert_checkbox = QCheckBox("声音提醒")
        alert_type_layout = QHBoxLayout()
        alert_type_layout.addWidget(self.idle_visual_alert_checkbox)
        alert_type_layout.addWidget(self.idle_sound_alert_checkbox)
        alert_type_layout.addStretch()
        idle_reminder_layout.addLayout(alert_type_layout)

        self.idle_forceful_checkbox = QCheckBox("强力提醒 (关闭后若无操作将再次提醒)")
        self.idle_forceful_checkbox.setToolTip("启用后，如果您关闭了提醒窗口但没有开始新的计时，\n程序将在稍后再次提醒您，直到您开始为止。")
        
        forceful_layout = QHBoxLayout()
        forceful_layout.addWidget(self.idle_forceful_checkbox)
        
        self.idle_forceful_interval_spinbox = QSpinBox(self)
        self.idle_forceful_interval_spinbox.setRange(1, 15)
        self.idle_forceful_interval_spinbox.setSuffix(" 分钟")
        self.idle_forceful_interval_spinbox.setToolTip("设置强力提醒的重复间隔。")
        
        forceful_layout.addWidget(self.idle_forceful_interval_spinbox)
        forceful_layout.addStretch()
        idle_reminder_layout.addLayout(forceful_layout)
        
        # Connect enable checkbox to enable/disable other controls in this group
        self.idle_reminder_enabled_checkbox.toggled.connect(self.idle_threshold_spinbox.setEnabled)
        self.idle_reminder_enabled_checkbox.toggled.connect(self.idle_visual_alert_checkbox.setEnabled)
        self.idle_reminder_enabled_checkbox.toggled.connect(self.idle_sound_alert_checkbox.setEnabled)
        self.idle_reminder_enabled_checkbox.toggled.connect(self.idle_forceful_checkbox.setEnabled)
        
        # The forceful interval spinbox should only be enabled if the forceful checkbox itself is checked
        self.idle_forceful_checkbox.toggled.connect(self.idle_forceful_interval_spinbox.setEnabled)

        idle_reminder_group.setLayout(idle_reminder_layout)
        layout.addWidget(idle_reminder_group)

        # --- Break End Notification Settings ---
        break_end_group = QGroupBox("休息结束提醒")
        break_end_layout = QVBoxLayout()
        
        self.notification_checkbox = QCheckBox("启用此功能")
        break_end_layout.addWidget(self.notification_checkbox)

        mode_groupbox = QGroupBox("提醒模式")
        mode_v_layout = QVBoxLayout()
        self.radio_play_once = QRadioButton("播放一次")
        self.radio_loop_play = QRadioButton("循环播放 (无限)")
        loop_n_layout = QHBoxLayout()
        self.radio_loop_n = QRadioButton("循环播放")
        self.loop_n_spinbox = QSpinBox(self)
        self.loop_n_spinbox.setRange(1, 99)
        self.loop_n_spinbox.setSuffix(" 次")
        loop_n_layout.addWidget(self.radio_loop_n)
        loop_n_layout.addWidget(self.loop_n_spinbox)
        mode_v_layout.addWidget(self.radio_play_once)
        mode_v_layout.addWidget(self.radio_loop_play)
        mode_v_layout.addLayout(loop_n_layout)
        mode_groupbox.setLayout(mode_v_layout)
        break_end_layout.addWidget(mode_groupbox)
        break_end_group.setLayout(break_end_layout)
        layout.addWidget(break_end_group)

        # Connect enable checkbox to enable/disable other controls in this group
        self.notification_checkbox.toggled.connect(mode_groupbox.setEnabled)

        self.reminder_mode_group = QButtonGroup(self)
        self.reminder_mode_group.addButton(self.radio_play_once, 1)
        self.reminder_mode_group.addButton(self.radio_loop_play, 2)
        self.reminder_mode_group.addButton(self.radio_loop_n, 3)

        volume_label = QLabel("音量")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        layout.addWidget(volume_label)
        layout.addWidget(self.volume_slider)

        output_device_groupbox = QGroupBox("音频输出设备")
        output_device_layout = QVBoxLayout()
        self.output_device_combo = QComboBox()
        self.populate_output_devices()
        output_device_layout.addWidget(self.output_device_combo)
        output_device_groupbox.setLayout(output_device_layout)
        layout.addWidget(output_device_groupbox)

        self.test_button = QPushButton("测试声音")
        layout.addWidget(self.test_button)
        layout.addStretch()
        return page

    def create_general_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        # --- General App Behavior ---
        app_behavior_group = QGroupBox("应用行为")
        app_behavior_layout = QVBoxLayout()

        self.startup_checkbox = QCheckBox("开机自启")
        self.startup_checkbox.setToolTip("设置应用是否在您登录Windows时自动启动。")
        app_behavior_layout.addWidget(self.startup_checkbox)

        self.minimize_on_auto_start_checkbox = QCheckBox("开机自启动时最小化")
        self.minimize_on_auto_start_checkbox.setToolTip("当应用随系统自动启动时，窗口将自动最小化。")
        app_behavior_layout.addWidget(self.minimize_on_auto_start_checkbox)

        self.minimize_on_manual_start_checkbox = QCheckBox("手动启动时最小化")
        self.minimize_on_manual_start_checkbox.setToolTip("当您手动打开应用时，窗口将自动最小化。")
        app_behavior_layout.addWidget(self.minimize_on_manual_start_checkbox)
        
        self.force_rest_checkbox = QCheckBox("启用强制休息 (番茄钟模式下，工作结束后强制进入休息)")
        app_behavior_layout.addWidget(self.force_rest_checkbox)

        app_behavior_group.setLayout(app_behavior_layout)
        layout.addWidget(app_behavior_group)

        # --- Data Folder Button ---
        data_folder_group = QGroupBox("数据与配置")
        data_folder_layout = QVBoxLayout()
        self.open_data_folder_button = QPushButton("打开应用数据文件夹")
        self.open_data_folder_button.setToolTip("打开存储日志、配置文件等应用数据的文件夹。")
        data_folder_layout.addWidget(self.open_data_folder_button)
        data_folder_group.setLayout(data_folder_layout)
        layout.addWidget(data_folder_group)
 
        self.show_last_minute_window_checkbox = QCheckBox("显示最后一分钟悬浮窗")
        self.show_last_minute_window_checkbox.setToolTip("在倒计时的最后一分钟，显示一个迷你的悬浮倒计时窗口。")
        layout.addWidget(self.show_last_minute_window_checkbox)

        # --- Floating Window Settings ---
        self.floating_window_settings_group = QGroupBox("悬浮窗设置")
        floating_window_layout = QFormLayout()

        # Position
        self.floating_window_pos_combo = QComboBox()
        self.floating_window_pos_combo.addItems(["右上角", "左上角", "右下角", "左下角", "居中", "左侧居中", "右侧居中"])
        self.floating_window_pos_combo.setProperty("setting_keys", ["top_right", "top_left", "bottom_right", "bottom_left", "center", "left_center", "right_center"])
        floating_window_layout.addRow("默认位置:", self.floating_window_pos_combo)

        # Size
        self.floating_window_size_slider = QSlider(Qt.Horizontal)
        self.floating_window_size_slider.setRange(50, 200) # 50% to 200%
        self.floating_window_size_slider.setSingleStep(10)
        self.floating_window_size_slider.setTickPosition(QSlider.TicksBelow)
        self.floating_window_size_slider.setTickInterval(50)
        floating_window_layout.addRow("大小缩放:", self.floating_window_size_slider)

        self.preview_button = QPushButton("预览")
        floating_window_layout.addWidget(self.preview_button)
        
        self.floating_window_settings_group.setLayout(floating_window_layout)
        layout.addWidget(self.floating_window_settings_group)

        self.show_last_minute_window_checkbox.toggled.connect(self.floating_window_settings_group.setEnabled)

        layout.addStretch()
        return page

    def populate_output_devices(self):
        self.output_device_combo.clear()
        self.output_device_combo.addItem("默认设备", -1)
        try:
            devices = get_output_devices()
            for device in devices:
                self.output_device_combo.addItem(f"{device['name']}", device['index'])
        except Exception as e:
            print(f"无法加载音频设备: {e}")

    def connect_signals(self):
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.test_button.clicked.connect(self.toggle_test_sound)
        self.sound_player.playback_finished.connect(self.on_test_sound_finished)
        # Link custom mode radio button to enable/disable the custom settings groupbox
        self.advanced_mode_checkbox.toggled.connect(self.mode_groupbox.setEnabled)
        self.advanced_mode_checkbox.toggled.connect(self.mode_description_label.setEnabled)
        self.mode_button_group.buttonClicked.connect(self.update_mode_description)
        # --- 自动启用高级模式 ---
        # 当用户在高级模式列表中做出选择时，自动勾选“启用高级模式”复选框。
        # 这改善了用户体验，避免了用户需要手动勾选才能使模式选择生效的困惑。
        self.mode_button_group.buttonClicked.connect(self._enable_advanced_mode_on_selection)
        self.preview_button.clicked.connect(self.show_preview)
        self.open_data_folder_button.clicked.connect(self.open_data_folder)

    def _enable_advanced_mode_on_selection(self):
        """当用户点击任何模式单选按钮时，自动启用高级模式。"""
        if not self.advanced_mode_checkbox.isChecked():
            self.advanced_mode_checkbox.setChecked(True)
 
    def load_settings(self):
        # Mode
        advanced_enabled = self.staged_settings.get("advanced_mode_enabled", False)
        self.advanced_mode_checkbox.setChecked(advanced_enabled)
        self.mode_groupbox.setEnabled(advanced_enabled)

        if advanced_enabled:
            active_mode_key = self.staged_settings["active_mode_key"]
            active_mode = OperatingMode.from_key(active_mode_key)
            
            # 查找与活动模式键关联的单选按钮
            button_to_check = None
            for rb, mode_key_in_map in self.radio_button_to_mode_key_map.items():
                if mode_key_in_map == active_mode_key:
                    button_to_check = rb
                    break
            
            if button_to_check:
                button_to_check.setChecked(True)
            elif self.custom_rb: # 如果找不到，默认选中自定义模式
                self.custom_rb.setChecked(True)
        
        # Initial state for custom cycle groupbox, depends on both advanced mode and custom radio button
        self.update_mode_description() # Update description and visibility on load

        # Custom Cycle
        cycle_config = self.yasumi_clock_config.get("presets", {}).get("custom", {})
        self.work_mins_spinbox.setValue(cycle_config.get("work_mins", 25))
        self.short_break_spinbox.setValue(cycle_config.get("short_break_mins", 5))
        self.long_break_spinbox.setValue(cycle_config.get("long_break_mins", 15))
        self.cycles_spinbox.setValue(cycle_config.get("cycles_before_long_break", 4))

        # Notification
        notification_config = self.yasumi_clock_config.get("notification", {})
        break_end_enabled = notification_config.get("enabled", True)
        self.notification_checkbox.setChecked(break_end_enabled)
        # Find the groupbox to disable
        mode_groupbox = self.radio_play_once.parentWidget()
        if isinstance(mode_groupbox, QGroupBox):
            mode_groupbox.setEnabled(break_end_enabled)

        self.volume_slider.setValue(notification_config.get("volume", 80))
        mode = notification_config.get("mode", "play_once")
        if mode == "loop_play": self.radio_loop_play.setChecked(True)
        elif mode == "loop_n_times": self.radio_loop_n.setChecked(True)
        else: self.radio_play_once.setChecked(True)
        self.loop_n_spinbox.setValue(notification_config.get("loop_count", 3))
        output_device_id = notification_config.get("output_device_id", -1)
        index_to_set = self.output_device_combo.findData(output_device_id)
        self.output_device_combo.setCurrentIndex(index_to_set if index_to_set != -1 else 0)

        # Idle Reminder
        idle_reminder_config = self.yasumi_clock_config.get("idle_reminder", {})
        idle_enabled = idle_reminder_config.get("enabled", True)
        self.idle_reminder_enabled_checkbox.setChecked(idle_enabled)
        self.idle_threshold_spinbox.setValue(idle_reminder_config.get("threshold_mins", 5))
        self.idle_visual_alert_checkbox.setChecked(idle_reminder_config.get("visual_alert", True))
        self.idle_sound_alert_checkbox.setChecked(idle_reminder_config.get("sound_alert", True))
        forceful_enabled = idle_reminder_config.get("forceful_reminder", False)
        self.idle_forceful_checkbox.setChecked(forceful_enabled)
        self.idle_forceful_interval_spinbox.setValue(idle_reminder_config.get("forceful_interval_mins", 2))
        
        # Set initial enabled state of idle reminder controls
        self.idle_threshold_spinbox.setEnabled(idle_enabled)
        self.idle_visual_alert_checkbox.setEnabled(idle_enabled)
        self.idle_sound_alert_checkbox.setEnabled(idle_enabled)
        self.idle_forceful_checkbox.setEnabled(idle_enabled)
        # The interval spinbox depends on both the main toggle and the forceful toggle
        self.idle_forceful_interval_spinbox.setEnabled(idle_enabled and forceful_enabled)

        # General
        # General - App Behavior
        self.force_rest_checkbox.setChecked(self.yasumi_clock_config.get("force_rest", False))
        self.minimize_on_auto_start_checkbox.setChecked(self.yasumi_clock_config.get("minimize_on_auto_start", True)) # 默认为True
        self.minimize_on_manual_start_checkbox.setChecked(self.yasumi_clock_config.get("minimize_on_manual_start", False)) # 默认为False
        # "Yasumi Clock" is the app name used for registry, ensure it's consistent
        self.startup_checkbox.setChecked(get_startup_status("Yasumi Clock"))

        # Floating window settings
        show_floating_window = self.yasumi_clock_config.get("show_last_minute_window", False)
        self.show_last_minute_window_checkbox.setChecked(show_floating_window)
        self.floating_window_settings_group.setEnabled(show_floating_window)

        floating_window_config = self.yasumi_clock_config.get("floating_window", {})
        
        # Load position
        position_key = floating_window_config.get("position", "top_right")
        position_keys = self.floating_window_pos_combo.property("setting_keys")
        if position_key in position_keys:
            self.floating_window_pos_combo.setCurrentIndex(position_keys.index(position_key))
        
        # Load size
        size_scale = floating_window_config.get("size_scale", 1.0)
        self.floating_window_size_slider.setValue(int(size_scale * 100))

    def save_settings(self):
        advanced_enabled = self.advanced_mode_checkbox.isChecked()
        self.staged_settings["advanced_mode_enabled"] = advanced_enabled

        if advanced_enabled:
            checked_button = self.mode_button_group.checkedButton()
            if checked_button and checked_button in self.radio_button_to_mode_key_map:
                selected_mode_key = self.radio_button_to_mode_key_map[checked_button]
                self.staged_settings["active_mode_key"] = selected_mode_key
            else:
                # 如果没有选中的，默认给一个
                self.staged_settings["active_mode_key"] = OperatingMode.CUSTOM.value
        else:
            self.staged_settings["active_mode_key"] = OperatingMode.CLASSIC.value

        user_settings = {
            "yasumi_clock": {
                "advanced_mode_enabled": advanced_enabled,
                "active_mode_key": self.staged_settings["active_mode_key"],
                "force_rest": self.force_rest_checkbox.isChecked(),
                "minimize_on_auto_start": self.minimize_on_auto_start_checkbox.isChecked(),
                "minimize_on_manual_start": self.minimize_on_manual_start_checkbox.isChecked(),
                "show_last_minute_window": self.show_last_minute_window_checkbox.isChecked(),
                "floating_window": {
                    "position": self.floating_window_pos_combo.property("setting_keys")[self.floating_window_pos_combo.currentIndex()],
                    "size_scale": self.floating_window_size_slider.value() / 100.0
                },
                "idle_reminder": {
                    "enabled": self.idle_reminder_enabled_checkbox.isChecked(),
                    "threshold_mins": self.idle_threshold_spinbox.value(),
                    "visual_alert": self.idle_visual_alert_checkbox.isChecked(),
                    "sound_alert": self.idle_sound_alert_checkbox.isChecked(),
                    "forceful_reminder": self.idle_forceful_checkbox.isChecked(),
                    "forceful_interval_mins": self.idle_forceful_interval_spinbox.value()
                },
                "notification": {
                    "enabled": self.notification_checkbox.isChecked(),
                    "volume": self.volume_slider.value(),
                    "loop_count": self.loop_n_spinbox.value(),
                    "output_device_id": self.output_device_combo.currentData(),
                    "mode": "loop_play" if self.radio_loop_play.isChecked() else \
                            "loop_n_times" if self.radio_loop_n.isChecked() else \
                            "play_once"
                },
                "presets": {
                    "custom": {
                        "work_mins": self.work_mins_spinbox.value(),
                        "short_break_mins": self.short_break_spinbox.value(),
                        "long_break_mins": self.long_break_spinbox.value(),
                        "cycles_before_long_break": self.cycles_spinbox.value()
                    }
                }
            }
        }
        self.config_manager.save_user_config(user_settings)

        # Handle startup setting separately as it modifies the system registry
        try:
            # Ensure you use a consistent app name
            set_startup_status("Yasumi Clock", self.startup_checkbox.isChecked())
        except Exception as e:
            print(f"Failed to update startup status: {e}")

    def accept(self):
        if self.sound_player.is_playing():
            self.sound_player.stop()
        self.save_settings()
        super().accept()

    def reject(self):
        if self.sound_player.is_playing():
            self.sound_player.stop()
        super().reject()

    def toggle_test_sound(self):
        if self.sound_player.is_playing():
            self.sound_player.stop()
            # on_test_sound_finished will be called by the player's on_finish callback
        else:
            volume = self.volume_slider.value()
            device_id = self.output_device_combo.currentData()
            sound_path = self.config_manager.get_resource_path("src/audio/game-level-complete.wav")

            # Determine loop count from UI settings
            if self.radio_loop_play.isChecked():
                loop_count = -1  # Infinite loop
            elif self.radio_loop_n.isChecked():
                loop_count = self.loop_n_spinbox.value()
            else: # self.radio_play_once.isChecked()
                loop_count = 1

            self.test_button.setText("停止测试")
            self.sound_player.play(
                sound_path=str(sound_path),
                volume=volume,
                loop_count=loop_count,
                device_id=device_id if device_id != -1 else None
            )

    def on_test_sound_finished(self):
        self.test_button.setText("测试声音")

    def show_help_text(self, text):
        self.mode_description_label.setText(text)

    def update_mode_description(self, button=None):
        # The 'button' argument is passed by the buttonClicked signal
        checked_button = self.mode_button_group.checkedButton()
        is_custom_mode_selected = False
        
        if checked_button and checked_button in self.radio_button_to_mode_key_map:
            selected_mode_key = self.radio_button_to_mode_key_map[checked_button]
            
            # 从配置中获取描述
            mode_config = self.yasumi_clock_config.get("presets", {}).get(selected_mode_key, {})
            description = mode_config.get("description", "该模式的说明未在配置中找到。")
            self.mode_description_label.setText(description.strip())
            
            if selected_mode_key == 'custom':
                is_custom_mode_selected = True
        else:
            # Fallback text if no button is selected
            self.mode_description_label.setText("请选择一个模式，这里会显示它的玩法说明哦。")

        # Show/hide the custom settings groupbox based on whether "Custom" mode is selected
        self.custom_cycle_groupbox.setVisible(is_custom_mode_selected)

    def open_data_folder(self):
        """打开包含应用数据的文件夹"""
        folder_path = self.config_manager.user_data_dir
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(folder_path)
            elif system == "Darwin": # macOS
                subprocess.call(["open", folder_path])
            else: # Linux
                subprocess.call(["xdg-open", folder_path])
        except Exception as e:
            print(f"无法打开文件夹: {e}")

    def show_preview(self):
        """显示悬浮窗的预览"""
        position_key = self.floating_window_pos_combo.property("setting_keys")[self.floating_window_pos_combo.currentIndex()]
        size_scale = self.floating_window_size_slider.value() / 100.0
        
        # 创建一个临时的预览窗口
        self.preview_window = FloatingWindow(position=position_key, size_scale=size_scale)
        self.preview_window.show()

        # --- 动态倒计时预览 ---
        self.preview_timer = QTimer(self)
        self.preview_countdown = 3 # 从3秒开始
        
        def update_preview_time():
            if self.preview_countdown > 0:
                self.preview_window.update_time(f"00:{self.preview_countdown:02d}")
                self.preview_countdown -= 1
            else:
                self.preview_timer.stop()
                self.preview_window.close()

        self.preview_timer.timeout.connect(update_preview_time)
        self.preview_timer.start(1000)
        update_preview_time() # 立即显示第一秒

    def closeEvent(self, event):
        if self.sound_player.is_playing():
            self.sound_player.stop()
        super().closeEvent(event)
