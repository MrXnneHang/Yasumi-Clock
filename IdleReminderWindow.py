import sys
import math
from PyQt5.QtWidgets import QWidget, QApplication, QVBoxLayout, QGraphicsDropShadowEffect, QLabel
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer
from PyQt5.QtGui import QPalette, QFont, QIcon, QPainter, QBrush, QLinearGradient, QColor, QTransform, QPen


class IdleReminderWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.setup_animations()

    # 动画属性
    @pyqtProperty(float)
    def pulse_opacity(self):
        return self._pulse_opacity

    @pulse_opacity.setter
    def pulse_opacity(self, value):
        self._pulse_opacity = value
        self.update()

    @pyqtProperty(float)
    def scale_factor(self):
        return self._scale_factor

    @scale_factor.setter
    def scale_factor(self, value):
        self._scale_factor = value
        self.update()

    @pyqtProperty(float)
    def glow_opacity(self):
        return self._glow_opacity

    @glow_opacity.setter
    def glow_opacity(self, value):
        self._glow_opacity = value
        self.update()

    def initUI(self):
        # 设置窗口属性
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # 设置窗口大小 - 紧凑的尺寸
        self.setFixedSize(360, 180)

        # 创建主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 30, 25, 30)
        layout.setSpacing(20)

        # 标题标签 - 调整为适合亚克力背景的深色文字
        self.title_label = QLabel("已经休息很久了，\n要不要开始下一个专注时段？", self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.title_label.setStyleSheet("""
            QLabel {
                color: #2C3E50;
                background: transparent;
                margin: 10px 0;
            }
        """)
        
        # 添加到布局
        layout.addWidget(self.title_label)
        self.setLayout(layout)
        self.center_on_screen()

        # 添加阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)


    def setup_animations(self):
        self._pulse_opacity = 1.0
        self._scale_factor = 1.0
        self._glow_opacity = 1.0
        # 窗口淡入动画
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(600)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # 脉冲动画
        self.pulse_animation = QPropertyAnimation(self, b"pulse_opacity")
        self.pulse_animation.setDuration(1500)
        self.pulse_animation.setStartValue(1.0)
        self.pulse_animation.setEndValue(0.5)
        self.pulse_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.pulse_animation.setLoopCount(-1)
        
        # 缩放动画
        self.scale_animation = QPropertyAnimation(self, b"scale_factor")
        self.scale_animation.setDuration(1000)
        self.scale_animation.setStartValue(1.0)
        self.scale_animation.setEndValue(1.02)
        self.scale_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.scale_animation.setLoopCount(-1)

        # 光晕动画
        self.glow_animation = QPropertyAnimation(self, b"glow_opacity")
        self.glow_animation.setDuration(1800)
        self.glow_animation.setStartValue(0.3)
        self.glow_animation.setEndValue(1.0)
        self.glow_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.glow_animation.setLoopCount(-1)

        QTimer.singleShot(50, self.fade_animation.start)
        QTimer.singleShot(100, self.pulse_animation.start)
        QTimer.singleShot(100, self.scale_animation.start)
        QTimer.singleShot(100, self.glow_animation.start)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制亚克力背景
        self.draw_fixed_background(painter)
        
    def draw_fixed_background(self, painter):
        """绘制现代化的亚克力背景"""
        main_rect = self.rect().adjusted(15, 15, -15, -15)

        # 保存原始变换
        original_transform = painter.transform()
        
        # 缩放变换
        transform = QTransform()
        transform.translate(self.width() / 2, self.height() / 2)
        transform.scale(self._scale_factor, self._scale_factor)
        transform.translate(-self.width() / 2, -self.height() / 2)
        painter.setTransform(transform)

        # 绘制脉冲光晕
        painter.setOpacity(self._pulse_opacity * 0.6)
        pulse_color = QColor(79, 195, 247, int(150 * self._pulse_opacity))
        painter.setBrush(QBrush(pulse_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(main_rect.adjusted(-5, -5, 5, 5), 20, 20)
        
        # 恢复透明度
        painter.setOpacity(1.0)

        # 绘制主窗口背景
        gradient = QLinearGradient(0, main_rect.top(), 0, main_rect.bottom())
        gradient.setColorAt(0, QColor(245, 245, 255, 220))
        gradient.setColorAt(1, QColor(220, 230, 250, 200))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(main_rect, 15, 15)

        # 绘制内层毛玻璃效果
        inner_glow_rect = main_rect.adjusted(2, 2, -2, -2)
        inner_gradient = QLinearGradient(0, inner_glow_rect.top(), 0, inner_glow_rect.bottom())
        inner_gradient.setColorAt(0, QColor(255, 255, 255, 160))
        inner_gradient.setColorAt(1, QColor(245, 250, 255, 120))
        painter.setBrush(QBrush(inner_gradient))
        painter.drawRoundedRect(inner_glow_rect, 13, 13)

        # 绘制发光边框
        painter.setOpacity(self._glow_opacity)
        pen = QPen(QColor(79, 195, 247, int(220 * self._glow_opacity)))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(main_rect.adjusted(1, 1, -1, -1), 15, 15)
        painter.setOpacity(1.0)
        
        # 绘制内层高光边框
        pen.setColor(QColor(255, 255, 255, 180))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(main_rect.adjusted(2, 2, -2, -2), 14, 14)

        # 恢复原始变换
        painter.setTransform(original_transform)

    def center_on_screen(self):
        # 将窗口居中
        screen_geometry = QApplication.desktop().screenGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

    def mousePressEvent(self, event):
        # 点击窗口任意位置即可关闭
        self.close()