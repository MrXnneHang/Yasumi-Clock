import sys
import os
from pathlib import Path
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtGui import QPixmap, QImage
from qfluentwidgets import PrimaryPushButton, PushButton

import numpy as np
from PIL import Image

from util import set_pos,calculate_screen_scaling_ratio, ConfigManager

class Main_Window_UI(QtWidgets.QWidget):
    """主窗口的UI布局

    属性:
    self.animation_play_thread:播放play动画的线程
    self.animation_work_thread:播放work动画的线程
    
    用法:
    作为Main UI Response的父类
    """
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.window_config = self.config_manager.get_config()
        self.src_config = self.config_manager.get_src_config()

        # Window pos
        self.yasumi_clock_config = self.window_config["yasumi_clock"]
        self.main_window = self.yasumi_clock_config["main_window"]
        self.animation_pos = self.main_window["animation"]

        # Image Source
        self.animation_play_path = self.config_manager.get_resource_path(self.src_config["play"])
        self.animation_work_path = self.config_manager.get_resource_path(self.src_config["work"])
        self.animation_path = self.animation_play_path


    def initUI(self):
        self.setWindowTitle('Yasumi Clock')

        # Main layout
        main_layout = QtWidgets.QHBoxLayout(self)
        self.setLayout(main_layout)
        main_layout.setContentsMargins(20, 20, 20, 20) # 窗口外边距
        main_layout.setSpacing(20) # 左右面板间距

        # --- Left panel (animation) ---
        self.animation_label = QtWidgets.QLabel(self)
        self.animation_label.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(self.animation_label)

        # --- Right panel (controls) ---
        # 1. [核心改动] 创建一个专门的QWidget作为右侧面板的"卡片"容器
        self.right_panel_widget = QtWidgets.QWidget(self)
        self.right_panel_widget.setObjectName("RightPanel") # 为其命名，以便QSS应用样式
        # 设置右侧面板的尺寸策略，允许根据内容收缩
        self.right_panel_widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        right_panel_layout = QtWidgets.QVBoxLayout(self.right_panel_widget)
        self.right_panel_widget.setLayout(right_panel_layout)
        right_panel_layout.setContentsMargins(25, 25, 25, 25) # 卡片内部边距
        right_panel_layout.setSpacing(10) # 卡片内元素垂直间距
        main_layout.addWidget(self.right_panel_widget)

        # 2. [核心改动] 应用全新、统一的QSS样式表
        self.setStyleSheet("""
            /* 整体窗口和右侧面板卡片 */
            QWidget#RightPanel {
                background-color: #F8F9FA; /* 柔和的米白色背景，增加精致感 */
                border-radius: 10px;       /* 圆角是现代设计的灵魂 */
            }

            /* 主计时器 ("25:00" 或 "Begin!") */
            QLabel#timeLabel {
                font-size: 72px;            /* 使用巨大字号，形成视觉焦点 */
                font-weight: 300;           /* 使用纤细字重 (Light)，显得优雅不笨重 */
                color: #2C3E50;             /* 深邃的石板灰，比纯黑更柔和 */
                font-family: "Segoe UI Light", "Helvetica Neue", "Arial", sans-serif; /* 优先使用更现代的字体 */
            }

            /* 信息卡片容器 */
            QWidget#InfoCard {
                background-color: #FFFFFF;
                border: 1px solid #E8EAED;
                border-radius: 8px;
                margin: 0px;
            }
            
            /* 模式名称 - 主标题 */
            QLabel#ModeNameLabel {
                font-size: 14px;
                font-weight: 600;
                color: #1F2937;
                margin-bottom: 4px;
            }
            
            /* 配置标签 */
            QLabel#ConfigLabel {
                font-size: 10px;
                font-weight: 500;
                color: #6B7280;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            /* 配置数值 */
            QLabel#ConfigValue {
                font-size: 13px;
                font-weight: 700;
                color: #2563EB;
                margin-left: 4px;
            }
            
            /* 当前状态标签 */
            QLabel#CurrentStateLabel {
                font-size: 11px;
                font-weight: 600;
                color: #059669;
                background-color: #ECFDF5;
                border-radius: 8px;
                padding: 4px 10px;
                margin: 0px;
            }
            
            /* 进度指示器 */
            QLabel#progressIndicator {
                font-size: 14px;
                color: #5A6A7A;
                font-weight: 500;
            }
            
            /* [新增] 下一步预告标签 */
            QLabel#nextUpLabel {
                color: #888; 
                font-size: 12px;
                font-weight: 400;
            }

           /* [新增] 经典模式描述标签 */
           QLabel#ClassicDescriptionLabel {
               font-size: 13px;
               color: #6B7280;
               font-weight: 400;
           }

            /* 主要按钮 (开始) - 经典模式下缩小以配合+-按钮 */
            QPushButton#startFanqieButton {
                background-color: #00AEEF; /* 一个鲜活、和谐的蓝色 */
                color: white;
                font-size: 15px;            /* 稍微缩小字号 */
                font-weight: 600;           /* Semi-bold，突出主要操作 */
                padding: 10px 16px;         /* 缩小内边距 */
                border: none;
                border-radius: 20px;        /* 稍微缩小圆角 */
                min-height: 40px;           /* 缩小高度 */
                min-width: 80px;            /* 大幅缩小宽度，为+-按钮腾出空间 */
                max-width: 80px;            /* 限制最大宽度 */
            }
            QPushButton#startFanqieButton:hover {
                background-color: #009CDD;  /* 悬停时略微变暗，提供反馈 */
            }

            /* 次要按钮 (设置, 重置) - 简洁现代风格 */
            QPushButton#settingsButton, QPushButton#resetTimeButton {
                background-color: #F8F9FA;
                color: #495057;
                border: 2px solid #DEE2E6;
                font-size: 14px;
                font-weight: bold;
                padding: 14px 28px;
                border-radius: 20px;
                min-height: 44px;
                min-width: 100px;
            }

            QPushButton#settingsButton:hover, QPushButton#resetTimeButton:hover {
                background-color: #E9ECEF;
                color: #343A40;
                border-color: #ADB5BD;
            }

            QPushButton#settingsButton:pressed, QPushButton#resetTimeButton:pressed {
                background-color: #DEE2E6;
                color: #212529;
                border-color: #6C757D;
            }

            /* 设置按钮 - 蓝色主题 */
            QPushButton#settingsButton {
                background-color: #E3F2FD;
                color: #1976D2;
                border-color: #90CAF9;
            }

            QPushButton#settingsButton:hover {
                background-color: #BBDEFB;
                color: #1565C0;
                border-color: #64B5F6;
            }

            QPushButton#settingsButton:pressed {
                background-color: #90CAF9;
                color: #0D47A1;
                border-color: #42A5F5;
            }

            /* 重置按钮 - 红色主题 */
            QPushButton#resetTimeButton {
                background-color: #FFEBEE;
                color: #D32F2F;
                border-color: #FFCDD2;
            }

            QPushButton#resetTimeButton:hover {
                background-color: #FFCDD2;
                color: #C62828;
                border-color: #EF9A9A;
            }

            QPushButton#resetTimeButton:pressed {
                background-color: #EF9A9A;
                color: #B71C1C;
                border-color: #E57373;
            }
        """)

        # 3. [核心改动] 调整左右面板的拉伸因子，让右侧面板宽度固定，更显稳定
        main_layout.setStretch(0, 0) # 动画面板，不拉伸
        main_layout.setStretch(1, 0) # 控制面板，不拉伸

        # --- 4. [核心改动] 面板内部元素重组 ---

        # --- 顶部状态区 - 紧凑信息卡片 ---
        self.info_card = QtWidgets.QWidget(self)
        self.info_card.setObjectName("InfoCard")
        self.info_card.setMaximumHeight(120)  # 限制最大高度
        info_card_layout = QtWidgets.QVBoxLayout(self.info_card)
        info_card_layout.setContentsMargins(16, 12, 16, 12)
        info_card_layout.setSpacing(8)
        
        # 模式名称和状态 - 水平布局，基线对齐
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(12)
        
        self.modeNameLabel = QtWidgets.QLabel("", self)
        self.modeNameLabel.setObjectName("ModeNameLabel")
        self.modeNameLabel.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBaseline)
        header_layout.addWidget(self.modeNameLabel, 0, QtCore.Qt.AlignBaseline)
        
        header_layout.addStretch(1)
        
        self.currentStateLabel = QtWidgets.QLabel("", self)
        self.currentStateLabel.setObjectName("CurrentStateLabel")
        self.currentStateLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignBaseline)
        header_layout.addWidget(self.currentStateLabel, 0, QtCore.Qt.AlignBaseline)
        
        info_card_layout.addLayout(header_layout)
        
        # 配置信息 - 使用网格布局确保完美对齐
        self.config_widget = QtWidgets.QWidget()
        config_layout = QtWidgets.QGridLayout(self.config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setHorizontalSpacing(16)
        config_layout.setVerticalSpacing(4)
        
        # 专注时长
        work_label = QtWidgets.QLabel("专注", self)
        work_label.setObjectName("ConfigLabel")
        work_label.setAlignment(QtCore.Qt.AlignCenter)
        self.workTimeLabel = QtWidgets.QLabel("25min", self)
        self.workTimeLabel.setObjectName("ConfigValue")
        self.workTimeLabel.setAlignment(QtCore.Qt.AlignCenter)
        config_layout.addWidget(work_label, 0, 0)
        config_layout.addWidget(self.workTimeLabel, 1, 0)
        
        # 短休息
        short_label = QtWidgets.QLabel("短休", self)
        short_label.setObjectName("ConfigLabel")
        short_label.setAlignment(QtCore.Qt.AlignCenter)
        self.shortBreakLabel = QtWidgets.QLabel("5min", self)
        self.shortBreakLabel.setObjectName("ConfigValue")
        self.shortBreakLabel.setAlignment(QtCore.Qt.AlignCenter)
        config_layout.addWidget(short_label, 0, 1)
        config_layout.addWidget(self.shortBreakLabel, 1, 1)
        
        # 长休息
        long_label = QtWidgets.QLabel("长休", self)
        long_label.setObjectName("ConfigLabel")
        long_label.setAlignment(QtCore.Qt.AlignCenter)
        self.longBreakLabel = QtWidgets.QLabel("15min", self)
        self.longBreakLabel.setObjectName("ConfigValue")
        self.longBreakLabel.setAlignment(QtCore.Qt.AlignCenter)
        config_layout.addWidget(long_label, 0, 2)
        config_layout.addWidget(self.longBreakLabel, 1, 2)
        
        # 间隔
        cycle_label = QtWidgets.QLabel("间隔", self)
        cycle_label.setObjectName("ConfigLabel")
        cycle_label.setAlignment(QtCore.Qt.AlignCenter)
        self.cycleLabel = QtWidgets.QLabel("4轮", self)
        self.cycleLabel.setObjectName("ConfigValue")
        self.cycleLabel.setAlignment(QtCore.Qt.AlignCenter)
        config_layout.addWidget(cycle_label, 0, 3)
        config_layout.addWidget(self.cycleLabel, 1, 3)
        
        # 设置列的拉伸因子，让四列均匀分布
        for i in range(4):
            config_layout.setColumnStretch(i, 1)
        
        info_card_layout.addWidget(self.config_widget)

        # --- [New] Classic Mode Info Card ---
        self.classic_mode_info_widget = QtWidgets.QWidget()
        classic_info_layout = QtWidgets.QVBoxLayout(self.classic_mode_info_widget)
        classic_info_layout.setContentsMargins(0, 10, 0, 10) # Add some vertical margin
        classic_info_layout.setSpacing(8)

        classic_desc = QtWidgets.QLabel("一个纯粹的计时器，\n点击开始，沉浸专注。", self)
        classic_desc.setObjectName("ClassicDescriptionLabel")
        classic_desc.setWordWrap(True)
        classic_desc.setAlignment(QtCore.Qt.AlignCenter)
        classic_info_layout.addWidget(classic_desc)
        
        info_card_layout.addWidget(self.classic_mode_info_widget)
        self.classic_mode_info_widget.hide() # Initially hide it
        
        right_panel_layout.addWidget(self.info_card)

        # --- 核心交互区 - 紧凑布局 ---
        # 添加适量间距
        right_panel_layout.addSpacing(10)
        
        # 主时间显示
        self.timeLabel = QtWidgets.QLabel("Begin!", self)
        self.timeLabel.setObjectName("timeLabel")
        self.timeLabel.setAlignment(QtCore.Qt.AlignCenter)
        right_panel_layout.addWidget(self.timeLabel)
        
        # 进度和下一步信息 - 垂直紧凑布局
        progress_container = QtWidgets.QWidget()
        progress_layout = QtWidgets.QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)
        
        self.progressIndicator = QtWidgets.QLabel("○ ○ ○ ○", self)
        self.progressIndicator.setObjectName("progressIndicator")
        self.progressIndicator.setAlignment(QtCore.Qt.AlignCenter)
        progress_layout.addWidget(self.progressIndicator)

        self.nextUpLabel = QtWidgets.QLabel("点击开始专注", self)
        self.nextUpLabel.setObjectName("nextUpLabel")
        self.nextUpLabel.setAlignment(QtCore.Qt.AlignCenter)
        progress_layout.addWidget(self.nextUpLabel)
        
        right_panel_layout.addWidget(progress_container)
        
        # 添加弹性空间，但减少数量
        right_panel_layout.addSpacing(40)

        # --- 主操作区 - 简化设计 ---
        # 主开始按钮 - 独立显示，更突出
        main_button_layout = QtWidgets.QHBoxLayout()
        main_button_layout.addStretch(1)
        
        self.startFanqieButton = QtWidgets.QPushButton('开始', self)
        self.startFanqieButton.setObjectName("startFanqieButton")
        self.startFanqieButton.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                font-size: 16px;
                font-weight: 600;
                padding: 12px 32px;
                border-radius: 12px;
                min-height: 48px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2E6BB0;
            }
        """)
        
        main_button_layout.addWidget(self.startFanqieButton)
        main_button_layout.addStretch(1)
        
        right_panel_layout.addLayout(main_button_layout)
        
        # 时间调整按钮 - 小巧的辅助按钮
        time_adjust_layout = QtWidgets.QHBoxLayout()
        time_adjust_layout.setSpacing(8)
        time_adjust_layout.addStretch(1)
        
        self.subTimeButton = QtWidgets.QPushButton('−5min', self)
        self.subTimeButton.setStyleSheet("""
            QPushButton {
                background-color: #F8F9FA;
                color: #6C757D;
                border: 1px solid #DEE2E6;
                font-size: 12px;
                font-weight: 500;
                padding: 6px 12px;
                border-radius: 6px;
                min-height: 28px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #E9ECEF;
                color: #495057;
            }
        """)
        
        self.addTimeButton = QtWidgets.QPushButton('+5min', self)
        self.addTimeButton.setStyleSheet("""
            QPushButton {
                background-color: #F8F9FA;
                color: #6C757D;
                border: 1px solid #DEE2E6;
                font-size: 12px;
                font-weight: 500;
                padding: 6px 12px;
                border-radius: 6px;
                min-height: 28px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #E9ECEF;
                color: #495057;
            }
        """)
        
        time_adjust_layout.addWidget(self.subTimeButton)
        time_adjust_layout.addWidget(self.addTimeButton)
        time_adjust_layout.addStretch(1)
        
        right_panel_layout.addLayout(time_adjust_layout)
        
        # 添加间距
        right_panel_layout.addSpacing(15)

        # --- 次要操作区 - 简洁底部按钮 ---
        secondary_actions_layout = QtWidgets.QHBoxLayout()
        secondary_actions_layout.setSpacing(12)
        secondary_actions_layout.addStretch(1)

        self.resetTimeButton = QtWidgets.QPushButton('重置', self)
        self.resetTimeButton.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9CA3AF;
                border: none;
                font-size: 13px;
                font-weight: 500;
                padding: 8px 16px;
                border-radius: 6px;
                min-height: 32px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                color: #EF4444;
            }
            QPushButton:pressed {
                background-color: #E5E7EB;
                color: #DC2626;
            }
        """)
        
        self.settingsButton = QtWidgets.QPushButton('设置', self)
        self.settingsButton.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9CA3AF;
                border: none;
                font-size: 13px;
                font-weight: 500;
                padding: 8px 16px;
                border-radius: 6px;
                min-height: 32px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                color: #3B82F6;
            }
            QPushButton:pressed {
                background-color: #E5E7EB;
                color: #2563EB;
            }
        """)

        secondary_actions_layout.addWidget(self.resetTimeButton)
        secondary_actions_layout.addWidget(self.settingsButton)
        secondary_actions_layout.addStretch(1)
        
        right_panel_layout.addLayout(secondary_actions_layout)

        # 强制设置初始高度
        self.sync_panel_heights()
        
    def sync_panel_heights(self):
        """同步左右面板的高度"""
        # 设定一个固定的高度，以避免动态计算导致的高度不一致问题
        fixed_height = 480  # 设定一个足够容纳所有模式内容的高度
        self.right_panel_widget.setFixedHeight(fixed_height)
        self.animation_label.setMinimumHeight(fixed_height) # 确保左侧也同步
        self.layout().activate() # 强制布局刷新

    def update_mode_display(self, mode_info, state_text, cycles_text):
        """更新现代化的模式信息显示"""
        if isinstance(mode_info, dict):
            # 高级模式
            self.config_widget.show()
            self.classic_mode_info_widget.hide()
            
            # 更新模式名称
            self.modeNameLabel.setText(mode_info['mode_name'])
            
            # 更新配置信息
            self.workTimeLabel.setText(f"{mode_info['work_mins']}min")
            self.shortBreakLabel.setText(f"{mode_info['short_break_mins']}min")
            self.longBreakLabel.setText(f"{mode_info['long_break_mins']}min")
            self.cycleLabel.setText(f"{mode_info['cycles_before_long_break']}轮")
            
            # 更新当前状态
            self.currentStateLabel.setText(f"{state_text} {cycles_text}")
            self.currentStateLabel.show()
        else:
            # 经典模式
            self.config_widget.hide()
            self.classic_mode_info_widget.show()
            
            self.modeNameLabel.setText(str(mode_info))
            self.currentStateLabel.hide()
        
        self.sync_panel_heights()
    
    def update_status_and_adjust_size(self, text):
        """保持兼容性的方法"""
        # 这个方法现在主要用于经典模式
        pass
        
    def onMainWindowShow(self):
        # 当 mainWindow 显示时调用此槽函数
        if hasattr(self, 'loading_window') and self.loading_window.isVisible():
            self.loading_window.close()
