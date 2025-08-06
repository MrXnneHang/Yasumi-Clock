
import sys
import math
from PyQt5.QtWidgets import QWidget, QApplication, QVBoxLayout, QGraphicsDropShadowEffect, QLabel
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer
from PyQt5.QtGui import QPalette, QFont, QIcon, QPainter, QBrush, QLinearGradient, QColor
from qfluentwidgets import PushButton, InfoBar, InfoBarPosition

class StopSoundWindow(QWidget):
    def __init__(self, stop_callback):
        super().__init__()
        self.stop_callback = stop_callback
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
    
    # 波纹动画属性
    @pyqtProperty(float)
    def ripple1_radius(self):
        return self._ripple1_radius
    
    @ripple1_radius.setter
    def ripple1_radius(self, value):
        self._ripple1_radius = value
        self.update()
    
    @pyqtProperty(float)
    def ripple2_radius(self):
        return self._ripple2_radius
    
    @ripple2_radius.setter
    def ripple2_radius(self, value):
        self._ripple2_radius = value
        self.update()
    
    @pyqtProperty(float)
    def ripple3_radius(self):
        return self._ripple3_radius
    
    @ripple3_radius.setter
    def ripple3_radius(self, value):
        self._ripple3_radius = value
        self.update()
    
    @pyqtProperty(float)
    def ripple4_radius(self):
        return self._ripple4_radius
    
    @ripple4_radius.setter
    def ripple4_radius(self, value):
        self._ripple4_radius = value
        self.update()
    
    @pyqtProperty(float)
    def ripple5_radius(self):
        return self._ripple5_radius
    
    @ripple5_radius.setter
    def ripple5_radius(self, value):
        self._ripple5_radius = value
        self.update()
    
    @pyqtProperty(float)
    def ripple1_opacity(self):
        return self._ripple1_opacity
    
    @ripple1_opacity.setter
    def ripple1_opacity(self, value):
        self._ripple1_opacity = value
        self.update()
    
    @pyqtProperty(float)
    def ripple2_opacity(self):
        return self._ripple2_opacity
    
    @ripple2_opacity.setter
    def ripple2_opacity(self, value):
        self._ripple2_opacity = value
        self.update()
    
    @pyqtProperty(float)
    def ripple3_opacity(self):
        return self._ripple3_opacity
    
    @ripple3_opacity.setter
    def ripple3_opacity(self, value):
        self._ripple3_opacity = value
        self.update()
    
    @pyqtProperty(float)
    def ripple4_opacity(self):
        return self._ripple4_opacity
    
    @ripple4_opacity.setter
    def ripple4_opacity(self, value):
        self._ripple4_opacity = value
        self.update()
    
    @pyqtProperty(float)
    def ripple5_opacity(self):
        return self._ripple5_opacity
    
    @ripple5_opacity.setter
    def ripple5_opacity(self, value):
        self._ripple5_opacity = value
        self.update()
    

        
    def initUI(self):
        # 设置窗口属性
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 设置窗口大小 - 紧凑的尺寸
        self.setFixedSize(280, 320)
        
        # 创建主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # 标题标签 - 调整为适合亚克力背景的深色文字
        self.title_label = QLabel("🔊 正在播放\n- 休息结束提示音 -", self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.title_label.setStyleSheet("""
            QLabel {
                color: #2C3E50;
                background: transparent;
                margin: 10px 0;
                text-shadow: 0px 1px 1px rgba(255, 255, 255, 0.8);
            }
        """)
        
        # 创建停止按钮 - 使用与主应用一致的蓝色风格
        self.stopButton = PushButton("⏹ 停止", self)
        self.stopButton.clicked.connect(self.stop_sound)
        
        # 添加多重波纹动画效果
        self._pulse_opacity = 1.0
        self._scale_factor = 1.0
        self._glow_opacity = 1.0
        self._ripple1_radius = 0
        self._ripple2_radius = 0
        self._ripple3_radius = 0
        self._ripple4_radius = 0
        self._ripple5_radius = 0
        self._ripple1_opacity = 1.0
        self._ripple2_opacity = 1.0
        self._ripple3_opacity = 1.0
        self._ripple4_opacity = 1.0
        self._ripple5_opacity = 1.0
        

        
        # 脉冲动画
        self.pulse_animation = QPropertyAnimation(self, b"pulse_opacity")
        self.pulse_animation.setDuration(1200)
        self.pulse_animation.setStartValue(1.0)
        self.pulse_animation.setEndValue(0.3)
        self.pulse_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.pulse_animation.setLoopCount(-1)
        
        # 缩放动画
        self.scale_animation = QPropertyAnimation(self, b"scale_factor")
        self.scale_animation.setDuration(800)
        self.scale_animation.setStartValue(1.0)
        self.scale_animation.setEndValue(1.05)
        self.scale_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.scale_animation.setLoopCount(-1)
        
        # 光晕动画
        self.glow_animation = QPropertyAnimation(self, b"glow_opacity")
        self.glow_animation.setDuration(1500)
        self.glow_animation.setStartValue(0.2)
        self.glow_animation.setEndValue(1.0)
        self.glow_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.glow_animation.setLoopCount(-1)
        
        # 波纹1动画
        self.ripple1_animation = QPropertyAnimation(self, b"ripple1_radius")
        self.ripple1_animation.setDuration(2000)
        self.ripple1_animation.setStartValue(30)
        self.ripple1_animation.setEndValue(120)
        self.ripple1_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.ripple1_animation.setLoopCount(-1)
        
        self.ripple1_opacity_animation = QPropertyAnimation(self, b"ripple1_opacity")
        self.ripple1_opacity_animation.setDuration(2000)
        self.ripple1_opacity_animation.setStartValue(0.8)
        self.ripple1_opacity_animation.setEndValue(0.0)
        self.ripple1_opacity_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.ripple1_opacity_animation.setLoopCount(-1)
        
        # 波纹2动画 (延迟启动)
        self.ripple2_animation = QPropertyAnimation(self, b"ripple2_radius")
        self.ripple2_animation.setDuration(2000)
        self.ripple2_animation.setStartValue(30)
        self.ripple2_animation.setEndValue(120)
        self.ripple2_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.ripple2_animation.setLoopCount(-1)
        
        self.ripple2_opacity_animation = QPropertyAnimation(self, b"ripple2_opacity")
        self.ripple2_opacity_animation.setDuration(2000)
        self.ripple2_opacity_animation.setStartValue(0.8)
        self.ripple2_opacity_animation.setEndValue(0.0)
        self.ripple2_opacity_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.ripple2_opacity_animation.setLoopCount(-1)
        
        # 波纹3动画 (延迟启动)
        self.ripple3_animation = QPropertyAnimation(self, b"ripple3_radius")
        self.ripple3_animation.setDuration(2000)
        self.ripple3_animation.setStartValue(30)
        self.ripple3_animation.setEndValue(120)
        self.ripple3_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.ripple3_animation.setLoopCount(-1)
        
        self.ripple3_opacity_animation = QPropertyAnimation(self, b"ripple3_opacity")
        self.ripple3_opacity_animation.setDuration(2000)
        self.ripple3_opacity_animation.setStartValue(0.8)
        self.ripple3_opacity_animation.setEndValue(0.0)
        self.ripple3_opacity_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.ripple3_opacity_animation.setLoopCount(-1)
        
        # 波纹4动画 (更大范围的边缘波纹)
        self.ripple4_animation = QPropertyAnimation(self, b"ripple4_radius")
        self.ripple4_animation.setDuration(3000)
        self.ripple4_animation.setStartValue(50)
        self.ripple4_animation.setEndValue(180)
        self.ripple4_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.ripple4_animation.setLoopCount(-1)
        
        self.ripple4_opacity_animation = QPropertyAnimation(self, b"ripple4_opacity")
        self.ripple4_opacity_animation.setDuration(3000)
        self.ripple4_opacity_animation.setStartValue(0.6)
        self.ripple4_opacity_animation.setEndValue(0.0)
        self.ripple4_opacity_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.ripple4_opacity_animation.setLoopCount(-1)
        
        # 波纹5动画 (最外层边缘波纹)
        self.ripple5_animation = QPropertyAnimation(self, b"ripple5_radius")
        self.ripple5_animation.setDuration(4000)
        self.ripple5_animation.setStartValue(80)
        self.ripple5_animation.setEndValue(250)
        self.ripple5_animation.setEasingCurve(QEasingCurve.OutQuart)
        self.ripple5_animation.setLoopCount(-1)
        
        self.ripple5_opacity_animation = QPropertyAnimation(self, b"ripple5_opacity")
        self.ripple5_opacity_animation.setDuration(4000)
        self.ripple5_opacity_animation.setStartValue(0.4)
        self.ripple5_opacity_animation.setEndValue(0.0)
        self.ripple5_opacity_animation.setEasingCurve(QEasingCurve.OutQuart)
        self.ripple5_opacity_animation.setLoopCount(-1)
        

        

        
        # 启动所有动画，波纹动画错开时间
        self.pulse_animation.start()
        self.scale_animation.start()
        self.glow_animation.start()
        
        # 启动中心波纹动画
        QTimer.singleShot(0, self.ripple1_animation.start)
        QTimer.singleShot(0, self.ripple1_opacity_animation.start)
        QTimer.singleShot(600, self.ripple2_animation.start)
        QTimer.singleShot(600, self.ripple2_opacity_animation.start)
        QTimer.singleShot(1200, self.ripple3_animation.start)
        QTimer.singleShot(1200, self.ripple3_opacity_animation.start)
        
        # 启动边缘波纹动画
        QTimer.singleShot(800, self.ripple4_animation.start)
        QTimer.singleShot(800, self.ripple4_opacity_animation.start)
        QTimer.singleShot(1600, self.ripple5_animation.start)
        QTimer.singleShot(1600, self.ripple5_opacity_animation.start)
        

        
        # 设置按钮样式 - 更醒目的蓝色风格，带渐变和阴影
        self.stopButton.setStyleSheet("""
            PushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4FC3F7, stop:0.5 #1E90FF, stop:1 #1565C0);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.8);
                border-radius: 25px;
                font-size: 20px;
                font-weight: bold;
                min-width: 140px;
                min-height: 60px;
                font-family: Arial;
                padding: 15px 20px;
            }
            PushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #64B5F6, stop:0.5 #1C86EE, stop:1 #0D47A1);
                border: 2px solid rgba(255, 255, 255, 1.0);
            }
            PushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #42A5F5, stop:0.5 #1874CD, stop:1 #0A3D91);
                border: 2px solid rgba(255, 255, 255, 0.6);
            }
        """)
        
        # 添加阴影效果 - 调整为更柔和的阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.stopButton.setGraphicsEffect(shadow)
        
        # 提示标签 - 调整为适合亚克力背景的深色文字
        self.hint_label = QLabel("点击停止播放", self)
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setFont(QFont("Arial", 12))
        self.hint_label.setStyleSheet("""
            QLabel {
                color: #34495E;
                background: transparent;
                margin: 10px 0;
                font-weight: 500;
                text-shadow: 0px 1px 1px rgba(255, 255, 255, 0.6);
            }
        """)
        
        # 添加到布局
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.stopButton, 0, Qt.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.hint_label)
        
        self.setLayout(layout)
        self.center_on_screen()
        
    def setup_animations(self):
        # 窗口淡入动画
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # 启动淡入动画
        QTimer.singleShot(50, self.fade_animation.start)
    

        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制亚克力背景
        self.draw_fixed_background(painter)
        
        # 绘制中心按钮周围的波纹效果
        self.draw_center_ripples(painter)
    
    def draw_fixed_background(self, painter):
        """绘制亚克力色半透明背景"""
        # 绘制主窗口背景
        main_rect = self.rect().adjusted(15, 15, -15, -15)
        
        # 创建亚克力色半透明渐变背景
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(240, 248, 255, 180))    # 淡蓝白色，半透明
        gradient.setColorAt(0.3, QColor(230, 240, 250, 200))  # 稍深一点
        gradient.setColorAt(0.7, QColor(220, 235, 245, 200))  # 中间色调
        gradient.setColorAt(1, QColor(210, 230, 240, 180))    # 底部淡色
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(main_rect, 15, 15)
        
        # 绘制内层毛玻璃效果
        inner_glow_rect = main_rect.adjusted(3, 3, -3, -3)
        inner_gradient = QLinearGradient(0, 0, 0, self.height())
        inner_gradient.setColorAt(0, QColor(255, 255, 255, 120))  # 白色半透明
        inner_gradient.setColorAt(0.5, QColor(245, 250, 255, 100)) # 淡蓝白色
        inner_gradient.setColorAt(1, QColor(235, 245, 255, 120))   # 底部白色
        
        painter.setBrush(QBrush(inner_gradient))
        painter.drawRoundedRect(inner_glow_rect, 12, 12)
        
        # 绘制亚克力边框效果
        painter.setPen(QColor(79, 195, 247, 200))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(main_rect.adjusted(1, 1, -1, -1), 15, 15)
        
        # 绘制内层高光边框
        painter.setPen(QColor(255, 255, 255, 150))
        painter.drawRoundedRect(main_rect.adjusted(2, 2, -2, -2), 14, 14)
        
        # 添加顶部高光效果
        highlight_rect = main_rect.adjusted(5, 5, -5, -main_rect.height()//2)
        highlight_gradient = QLinearGradient(0, highlight_rect.top(), 0, highlight_rect.bottom())
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 100))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        
        painter.setBrush(QBrush(highlight_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(highlight_rect, 10, 10)
    


    
    def draw_center_ripples(self, painter):
        """绘制中心按钮周围的明显波纹效果"""
        if not hasattr(self, '_pulse_opacity'):
            return
            
        button_center = self.stopButton.geometry().center()
        
        # 绘制增强的中心波纹
        ripples = [
            (self._ripple1_radius, self._ripple1_opacity, QColor(30, 144, 255), 3),
            (self._ripple2_radius, self._ripple2_opacity, QColor(79, 195, 247), 2),
            (self._ripple3_radius, self._ripple3_opacity, QColor(135, 206, 250), 2),
            (self._ripple4_radius, self._ripple4_opacity, QColor(30, 144, 255), 1),
            (self._ripple5_radius, self._ripple5_opacity, QColor(79, 195, 247), 1)
        ]
        
        for radius, opacity, color, width in ripples:
            painter.setOpacity(opacity * 0.8)  # 增加透明度
            pen = painter.pen()
            pen.setColor(color)
            pen.setWidth(width)  # 设置线条宽度
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(int(button_center.x() - radius), 
                              int(button_center.y() - radius), 
                              int(radius * 2), int(radius * 2))
        
        # 绘制增强的按钮周围脉冲效果
        painter.setOpacity(self._pulse_opacity * 0.9)
        pulse_radius = int(60 * self._scale_factor)
        pen = painter.pen()
        pen.setColor(QColor(30, 144, 255, int(220 * self._pulse_opacity)))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(button_center.x() - pulse_radius//2, button_center.y() - 30, 
                              pulse_radius, 60, 25, 25)
        
        # 添加按钮内部光晕
        painter.setOpacity(self._glow_opacity * 0.4)
        inner_glow_radius = int(40 * self._scale_factor)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(135, 206, 250, int(100 * self._glow_opacity)))
        painter.drawEllipse(button_center.x() - inner_glow_radius//2, 
                          button_center.y() - inner_glow_radius//2,
                          inner_glow_radius, inner_glow_radius)
        
    def center_on_screen(self):
        # 将窗口居中
        screen_geometry = QApplication.desktop().screenGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
        
    def stop_sound(self):
        """手动停止铃声并关闭窗口"""
        # 立即停止铃声
        if self.stop_callback:
            self.stop_callback()
        
        # 淡出动画
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(400)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.finished.connect(self.close)
        
        # 稍微延迟执行淡出动画，让用户看到按钮被点击的效果
        QTimer.singleShot(200, self.fade_out_animation.start)
        
    def mousePressEvent(self, event):
        # 记录鼠标按下位置，用于拖动窗口
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        # 拖动窗口
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPos() - self.drag_position)
            event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    def test_callback():
        print("Stop button clicked!")
        
    # 创建窗口
    window = StopSoundWindow(test_callback)
    window.show()
    
    sys.exit(app.exec_())