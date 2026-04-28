from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QRubberBand
from PyQt5.QtGui import QPen, QColor, QPainter
from PyQt5.QtCore import Qt, QPoint, QRect, QPointF
from ui.items import FieldItem
from logic.commands import ModifyFieldCommand

class CustomScene(QGraphicsScene):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.guide_lines = []

    def add_guide_line(self, pos, is_vertical):
        pen = QPen(QColor("#0b50da"), 1.5, Qt.DashLine) 
        pen.setCosmetic(True) # Hace que las líneas guía se vean igual de finas al hacer zoom
        if is_vertical:
            line = self.addLine(pos, 0, pos, self.height(), pen)
        else:
            line = self.addLine(0, pos, self.width(), pos, pen)
        self.guide_lines.append(line)

    def clear_guides(self):
        for line in self.guide_lines:
            try:
                if line.scene():
                    self.removeItem(line)
            except RuntimeError: pass
        self.guide_lines.clear()

class PDFViewer(QGraphicsView):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.scene = CustomScene(main_window, self)
        self.setScene(self.scene)
        
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Ahora el zoom siempre se centra donde esté el cursor!
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.rubber_band.setStyleSheet("QRubberBand { background-color: rgba(11, 80, 218, 50); border: 2px solid #0b50da; }")
        
        self.origin = QPoint()
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        
        self.setStyleSheet("""
            QGraphicsView { 
                background-color: #e2e8f0; 
                border: none; 
            }
            QScrollBar:vertical { border: none; background: transparent; width: 10px; margin: 0px; }
            QScrollBar::handle:vertical { background: rgba(11, 80, 218, 0.2); border-radius: 5px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: rgba(11, 80, 218, 0.4); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar:horizontal { border: none; background: transparent; height: 10px; margin: 0px; }
            QScrollBar::handle:horizontal { background: rgba(11, 80, 218, 0.2); border-radius: 5px; min-width: 20px; }
            QScrollBar::handle:horizontal:hover { background: rgba(11, 80, 218, 0.4); }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.main_window.current_tool:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QRect(self.origin, self.origin))
            self.rubber_band.show()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.origin.isNull() and self.main_window.current_tool:
            rect = QRect(self.origin, event.pos()).normalized()
            self.rubber_band.setGeometry(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.main_window.current_tool:
            self.rubber_band.hide()
            rect = QRect(self.origin, event.pos()).normalized()
            self.origin = QPoint()
            
            if rect.width() < 10 or rect.height() < 10:
                return

            scene_rect = self.mapToScene(rect).boundingRect()
            self.main_window.create_field(scene_rect)
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        items = self.scene.selectedItems()
        if items and event.key() in [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down]:
            step = 1
            if event.modifiers() & Qt.ShiftModifier:
                step = 10
                
            dx = dy = 0
            if event.key() == Qt.Key_Left: dx = -step
            elif event.key() == Qt.Key_Right: dx = step
            elif event.key() == Qt.Key_Up: dy = -step
            elif event.key() == Qt.Key_Down: dy = step
            
            for item in items:
                if isinstance(item, FieldItem):
                    new_pos = item.pos() + QPointF(dx, dy)
                    cmd = ModifyFieldCommand(item, item.rect(), item.pos(), item.rect(), new_pos)
                    self.main_window.undo_stack.push(cmd)
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.main_window.zoom_in()
            else:
                self.main_window.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        if hasattr(self, 'main_window'):
            self.main_window.update_page_label()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile() and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.accept()
                return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.main_window.load_pdf(file_path)
                event.accept()
                return
        super().dropEvent(event)
