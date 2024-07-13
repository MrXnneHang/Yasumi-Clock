from PyQt5 import QtCore, QtGui, QtWidgets
from qfluentwidgets import PrimaryPushButton
class ManualSelectionWindow(QtWidgets.QWidget):
    def __init__(self, select_window_pos,child_button_pos):
        super().__init__()
        
        self.pos = select_window_pos
        self.button_pos = child_button_pos
        self.isSelecting = False
        self.startPos = None
        self.initUI()
        
        
    
    def initUI(self):
        self.setGeometry(self.pos[0]+600,
                         self.pos[1]+150,
                         self.pos[2],
                         self.pos[3])
        self.setWindowTitle('Manual Selection Tool')
        self.setStyleSheet("background-color: white;")

        self.selectionLabel = QtWidgets.QLabel(self)
        self.selectionLabel.setGeometry(QtCore.QRect(0, 0, 0, 0))
        self.selectionLabel.setStyleSheet("border: 2px dashed red;")
        for pos in self.button_pos:
            self.selectButton = PrimaryPushButton(self)
            self.selectButton.setGeometry(pos[0],pos[1],pos[2],pos[3])


        self.setMouseTracking(True)
    

    def mousePressEvent(self, event):
        self.isSelecting = True
        self.startPos = event.pos()
        self.selectionLabel.setGeometry(QtCore.QRect(self.startPos, QtCore.QSize()))

    def mouseMoveEvent(self, event):
        if self.isSelecting:
            rect = QtCore.QRect(self.startPos, event.pos()).normalized()
            self.selectionLabel.setGeometry(rect)

    def mouseReleaseEvent(self, event):
        if self.isSelecting:
            self.isSelecting = False
            endPos = event.pos()
            rect = QtCore.QRect(self.startPos, endPos).normalized()
            self.selectionLabel.setGeometry(rect)
            print(f"Selected Rectangle: {rect.x()}, {rect.y()}, {rect.width()}, {rect.height()}")
