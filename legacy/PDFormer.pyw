import sys
import subprocess
import time
import copy

# --- AUTO-INSTALADOR DE DEPENDENCIAS ---
def check_and_install_dependencies():
    required = {'fitz': 'PyMuPDF', 'PyQt5': 'PyQt5', 'qtawesome': 'qtawesome'}
    missing = []
    
    for mod, pkg in required.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
            
    if missing:
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, 
                f"Preparando PDFormer por primera vez...\n\n"
                f"Se van a instalar las librerías necesarias: {', '.join(missing)}.\n"
                "Haz clic en Aceptar y espera un momento. El programa se abrirá automáticamente al terminar.", 
                "Instalando dependencias - PDFormer", 0x40)
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        except Exception as e:
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, f"Error instalando los paquetes:\n{e}", "Error fatal", 0x10)
            sys.exit(1)

check_and_install_dependencies()

# --- IMPORTS PRINCIPALES ---
import fitz  # PyMuPDF
import qtawesome as qta # Librería para iconos profesionales (FontAwesome / Material)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QGraphicsView, 
                             QGraphicsScene, QAction, QMessageBox, QInputDialog, 
                             QRubberBand, QLabel, QGraphicsRectItem, QGraphicsItem, 
                             QGraphicsDropShadowEffect, QUndoStack, QUndoCommand, QMenu,
                             QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QGridLayout)
from PyQt5.QtGui import QImage, QPixmap, QColor, QBrush, QPen, QKeySequence, QFont, QCursor, QPainter, QTransform
from PyQt5.QtCore import Qt, QRect, QPoint, QPointF, QRectF, QSize

# ================= COMANDOS UNDO / REDO =================

class AddFieldCommand(QUndoCommand):
    def __init__(self, scene, item, all_fields):
        super().__init__("Añadir Elemento")
        self.scene = scene
        self.item = item
        self.all_fields = all_fields

    def redo(self):
        try:
            if self.item.scene() is None:
                self.scene.addItem(self.item)
            self.item.show()
            self.all_fields.add(self.item)
        except RuntimeError: pass

    def undo(self):
        try:
            if self.item.scene() == self.scene:
                self.scene.removeItem(self.item)
            self.all_fields.discard(self.item)
        except RuntimeError: pass

class RemoveFieldCommand(QUndoCommand):
    def __init__(self, scene, item, all_fields):
        super().__init__("Eliminar Elemento")
        self.scene = scene
        self.item = item
        self.all_fields = all_fields

    def redo(self):
        try:
            if self.item.scene() == self.scene:
                self.scene.removeItem(self.item)
            self.all_fields.discard(self.item)
        except RuntimeError: pass

    def undo(self):
        try:
            if self.item.scene() is None:
                self.scene.addItem(self.item)
            self.item.show()
            self.all_fields.add(self.item)
        except RuntimeError: pass

class ModifyFieldCommand(QUndoCommand):
    def __init__(self, item, old_rect, old_pos, new_rect, new_pos):
        super().__init__("Mover/Redimensionar")
        self.item = item
        self.old_rect = old_rect
        self.old_pos = old_pos
        self.new_rect = new_rect
        self.new_pos = new_pos

    def redo(self):
        try:
            self.item.setRect(self.new_rect)
            self.item.setPos(self.new_pos)
            if hasattr(self.item, 'update_handles_positions'):
                self.item.update_handles_positions()
        except RuntimeError: pass

    def undo(self):
        try:
            self.item.setRect(self.old_rect)
            self.item.setPos(self.old_pos)
            if hasattr(self.item, 'update_handles_positions'):
                self.item.update_handles_positions()
        except RuntimeError: pass

class ToggleBorderCommand(QUndoCommand):
    def __init__(self, item, new_state):
        super().__init__("Alternar Borde")
        self.item = item
        self.new_state = new_state
        self.old_state = not new_state

    def redo(self):
        try:
            self.item.has_border = self.new_state
            self.item.update_appearance()
        except RuntimeError: pass

    def undo(self):
        try:
            self.item.has_border = self.old_state
            self.item.update_appearance()
        except RuntimeError: pass

class ChangeTextCommand(QUndoCommand):
    def __init__(self, item, old_text, new_text):
        super().__init__("Cambiar Texto")
        self.item = item
        self.old_text = old_text
        self.new_text = new_text

    def redo(self):
        try:
            self.item.text_content = self.new_text
            self.item.update() 
        except RuntimeError: pass

    def undo(self):
        try:
            self.item.text_content = self.old_text
            self.item.update()
        except RuntimeError: pass


# ================= ELEMENTOS GRÁFICOS INTERACTIVOS =================

class ResizeHandle(QGraphicsRectItem):
    def __init__(self, position_type, parent):
        super().__init__(-5, -5, 10, 10, parent)
        self.position_type = position_type
        self.setBrush(QBrush(QColor("#0b50da"))) 
        
        pen = QPen(QColor("#FFFFFF"), 1.5)
        pen.setCosmetic(True) # Mantiene el borde de 1.5px sin importar el zoom visual
        self.setPen(pen)
        
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True) # Evita que los puntos se hagan gigantes con el zoom
        
        if position_type in ['tl', 'br']:
            self.setCursor(Qt.SizeFDiagCursor)
        elif position_type in ['tr', 'bl']:
            self.setCursor(Qt.SizeBDiagCursor)
        elif position_type in ['tc', 'bc']:
            self.setCursor(Qt.SizeVerCursor)
        elif position_type in ['lc', 'rc']:
            self.setCursor(Qt.SizeHorCursor)

class FieldItem(QGraphicsRectItem):
    def __init__(self, rect, field_type, field_name, options=None, has_border=True, text_content=""):
        super().__init__(rect)
        self.field_type = field_type
        self.field_name = field_name
        self.options = options
        self.has_border = has_border
        self.text_content = text_content

        self.update_appearance()
        
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        self.handles = {
            'tl': ResizeHandle('tl', self), 'tc': ResizeHandle('tc', self), 'tr': ResizeHandle('tr', self),
            'lc': ResizeHandle('lc', self),                                 'rc': ResizeHandle('rc', self),
            'bl': ResizeHandle('bl', self), 'bc': ResizeHandle('bc', self), 'br': ResizeHandle('br', self)
        }
        self.update_handles_positions()
        self.hide_handles()

        self.resizing = False
        self.active_handle = None
        self.start_rect = None
        self.start_pos = None

    def update_appearance(self):
        border_color = "#0b50da" 
        
        pen_solid = QPen(QColor(border_color), 1.5)
        pen_solid.setCosmetic(True) # Para que no engorde con el zoom
        
        pen_dashed = QPen(QColor(150, 150, 150, 150), 1, Qt.DashLine)
        pen_dashed.setCosmetic(True)
        
        if self.field_type == 'whiteout':
            self.setBrush(QBrush(QColor(255, 255, 255, 255))) 
            self.setPen(pen_solid if self.has_border else pen_dashed) 
        elif self.field_type == 'static_text':
            self.setBrush(QBrush(QColor(255, 255, 255, 1))) 
            self.setPen(pen_solid if self.has_border else pen_dashed) 
        elif self.field_type == 'signature':
            self.setBrush(QBrush(QColor(255, 235, 156, 160))) 
            self.setPen(pen_solid if self.has_border else QPen(Qt.NoPen))
        else:
            self.setBrush(QBrush(QColor(219, 234, 254, 160)))
            self.setPen(pen_solid if self.has_border else QPen(Qt.NoPen))

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.field_type == 'static_text' and self.text_content:
            painter.setRenderHint(QPainter.TextAntialiasing)
            painter.setPen(QPen(Qt.black))
            font = QFont("Segoe UI", 11)
            painter.setFont(font)
            painter.drawText(self.rect().adjusted(4, 4, -4, -4), Qt.TextWordWrap | Qt.AlignTop | Qt.AlignLeft, self.text_content)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px; font-family: 'Segoe UI'; }
            QMenu::item { padding: 8px 24px; border-radius: 4px; color: #0f172a; }
            QMenu::item:selected { background-color: #eff6ff; color: #0b50da; }
        """)
        action_text = "Quitar borde" if self.has_border else "Poner borde"
        toggle_action = menu.addAction(qta.icon('fa5s.border-all', color='#0f172a'), action_text)
        
        edit_text_action = None
        if self.field_type == 'static_text':
            edit_text_action = menu.addAction(qta.icon('fa5s.pen', color='#0f172a'), "Editar Texto")
            
        resize_action = menu.addAction(qta.icon('fa5s.ruler-combined', color='#0f172a'), "Definir tamaño...")
        
        action = menu.exec_(event.screenPos())
        
        if action == toggle_action:
            if hasattr(self.scene(), 'main_window'):
                mw = self.scene().main_window
                cmd = ToggleBorderCommand(self, not self.has_border)
                mw.undo_stack.push(cmd)
        elif edit_text_action and action == edit_text_action:
            if hasattr(self.scene(), 'main_window'):
                mw = self.scene().main_window
                new_text, ok = QInputDialog.getMultiLineText(mw, "Editar Texto Libre", "Escribe el nuevo texto:", self.text_content)
                if ok and new_text != self.text_content:
                    cmd = ChangeTextCommand(self, self.text_content, new_text)
                    mw.undo_stack.push(cmd)
        elif action == resize_action:
            if hasattr(self.scene(), 'main_window'):
                mw = self.scene().main_window
                current_w = int(self.rect().width())
                current_h = int(self.rect().height())
                
                dialog = QInputDialog(mw)
                dialog.setWindowTitle("Definir Tamaño")
                dialog.setLabelText("Nuevo tamaño (Ancho, Alto en px):")
                dialog.setTextValue(f"{current_w}, {current_h}")
                if dialog.exec_():
                    text = dialog.textValue()
                    try:
                        parts = text.split(',')
                        if len(parts) == 2:
                            w = float(parts[0].strip())
                            h = float(parts[1].strip())
                            if w >= 10 and h >= 10:
                                new_rect = QRectF(self.rect().x(), self.rect().y(), w, h)
                                cmd = ModifyFieldCommand(self, self.rect(), self.pos(), new_rect, self.pos())
                                mw.undo_stack.push(cmd)
                    except ValueError:
                        QMessageBox.warning(mw, "Error", "Formato inválido. Usa el formato: Ancho, Alto (Ej: 150, 50)")

    def update_handles_positions(self):
        r = self.rect()
        self.handles['tl'].setPos(r.topLeft())
        self.handles['tc'].setPos(r.center().x(), r.top())
        self.handles['tr'].setPos(r.topRight())
        
        self.handles['lc'].setPos(r.left(), r.center().y())
        self.handles['rc'].setPos(r.right(), r.center().y())
        
        self.handles['bl'].setPos(r.bottomLeft())
        self.handles['bc'].setPos(r.center().x(), r.bottom())
        self.handles['br'].setPos(r.bottomRight())

    def show_handles(self):
        for handle in self.handles.values(): handle.show()

    def hide_handles(self):
        for handle in self.handles.values(): handle.hide()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            if self.isSelected(): self.show_handles()
            else: self.hide_handles()
        
        if change == QGraphicsItem.ItemPositionChange and self.scene() and not self.resizing:
            new_pos = value
            mw = self.scene().main_window if hasattr(self.scene(), 'main_window') else None
            
            if hasattr(self.scene(), 'clear_guides'):
                self.scene().clear_guides()
                
            if mw and not mw.snap_enabled:
                return new_pos
            
            items = [i for i in self.scene().items() if isinstance(i, FieldItem) and i != self]
            if not items: return new_pos

            snap_threshold = 5
            my_rect = self.rect().translated(new_pos)
            my_center_x, my_center_y = my_rect.center().x(), my_rect.center().y()

            target_centers_x, target_edges_x, target_centers_y, target_edges_y = [], [], [], []

            for item in items:
                other_rect = item.sceneBoundingRect()
                if abs(my_rect.center().y() - other_rect.center().y()) < 2000: 
                    target_centers_x.append(other_rect.center().x())
                    target_edges_x.extend([other_rect.left(), other_rect.right()])
                    target_centers_y.append(other_rect.center().y())
                    target_edges_y.extend([other_rect.top(), other_rect.bottom()])

            snapped_x, snapped_y = False, False
            best_new_x, best_new_y = new_pos.x(), new_pos.y()
            guide_x, guide_y = None, None

            min_dx = snap_threshold
            for tx in target_centers_x:
                if abs(tx - my_center_x) < min_dx:
                    min_dx = abs(tx - my_center_x)
                    best_new_x = tx - self.rect().center().x()
                    guide_x = tx
                    snapped_x = True

            if not snapped_x:
                min_dx = snap_threshold
                for tx in target_edges_x:
                    for my_key, my_x in {'left': my_rect.left(), 'right': my_rect.right()}.items():
                        if abs(tx - my_x) < min_dx:
                            min_dx = abs(tx - my_x)
                            best_new_x = tx - (self.rect().left() if my_key == 'left' else self.rect().right())
                            guide_x = tx
                            snapped_x = True

            min_dy = snap_threshold
            for ty in target_centers_y:
                if abs(ty - my_center_y) < min_dy:
                    min_dy = abs(ty - my_center_y)
                    best_new_y = ty - self.rect().center().y()
                    guide_y = ty
                    snapped_y = True

            if not snapped_y:
                min_dy = snap_threshold
                for ty in target_edges_y:
                    for my_key, my_y in {'top': my_rect.top(), 'bottom': my_rect.bottom()}.items():
                        if abs(ty - my_y) < min_dy:
                            min_dy = abs(ty - my_y)
                            best_new_y = ty - (self.rect().top() if my_key == 'top' else self.rect().bottom())
                            guide_y = ty
                            snapped_y = True

            if snapped_x:
                new_pos.setX(best_new_x)
                self.scene().add_guide_line(guide_x, True)
            if snapped_y:
                new_pos.setY(best_new_y)
                self.scene().add_guide_line(guide_y, False)
                    
            return new_pos

        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.start_rect = self.rect()
        self.start_pos = self.pos()

        for handle in self.handles.values():
            if handle.isUnderMouse():
                self.resizing = True
                self.active_handle = handle.position_type
                event.accept()
                return

        if event.button() == Qt.LeftButton and event.modifiers() & Qt.ShiftModifier:
            if hasattr(self.scene(), 'main_window'):
                mw = self.scene().main_window
                clone = FieldItem(self.rect(), self.field_type, f"Copia_{int(time.time() * 1000)}", self.options, self.has_border, self.text_content)
                clone.setPos(self.pos())
                cmd = AddFieldCommand(self.scene(), clone, mw.all_fields)
                mw.undo_stack.push(cmd)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            mouse_pos = event.pos()
            scene_pos = self.mapToScene(mouse_pos)
            
            mw = self.scene().main_window if hasattr(self.scene(), 'main_window') else None
            if hasattr(self.scene(), 'clear_guides'): self.scene().clear_guides()
                
            if mw and mw.snap_enabled:
                items = [i for i in self.scene().items() if isinstance(i, FieldItem) and i != self]
                if items:
                    target_centers_x, target_edges_x, target_centers_y, target_edges_y = [], [], [], []
                    for item in items:
                        other_rect = item.sceneBoundingRect()
                        if abs(scene_pos.y() - other_rect.center().y()) < 2000:
                            target_centers_x.append(other_rect.center().x())
                            target_edges_x.extend([other_rect.left(), other_rect.right()])
                            target_centers_y.append(other_rect.center().y())
                            target_edges_y.extend([other_rect.top(), other_rect.bottom()])
                    
                    snap_threshold = 5
                    if self.active_handle in ['tl', 'tr', 'lc', 'rc', 'bl', 'br']:
                        min_dx = snap_threshold
                        best_x = scene_pos.x()
                        for tx in target_centers_x:
                            if abs(scene_pos.x() - tx) < min_dx:
                                min_dx, best_x = abs(scene_pos.x() - tx), tx
                        if min_dx == snap_threshold:
                            for tx in target_edges_x:
                                if abs(scene_pos.x() - tx) < min_dx:
                                    min_dx, best_x = abs(scene_pos.x() - tx), tx
                        if min_dx < snap_threshold:
                            scene_pos.setX(best_x)
                            self.scene().add_guide_line(best_x, True)

                    if self.active_handle in ['tl', 'tc', 'tr', 'bl', 'bc', 'br']:
                        min_dy = snap_threshold
                        best_y = scene_pos.y()
                        for ty in target_centers_y:
                            if abs(scene_pos.y() - ty) < min_dy:
                                min_dy, best_y = abs(scene_pos.y() - ty), ty
                        if min_dy == snap_threshold:
                            for ty in target_edges_y:
                                if abs(scene_pos.y() - ty) < min_dy:
                                    min_dy, best_y = abs(scene_pos.y() - ty), ty
                        if min_dy < snap_threshold:
                            scene_pos.setY(best_y)
                            self.scene().add_guide_line(best_y, False)
            
            mouse_pos = self.mapFromScene(scene_pos)
            rect = self.rect()

            if self.active_handle == 'tl': rect.setTopLeft(mouse_pos)
            elif self.active_handle == 'tc': rect.setTop(mouse_pos.y())
            elif self.active_handle == 'tr': rect.setTopRight(mouse_pos)
            elif self.active_handle == 'lc': rect.setLeft(mouse_pos.x())
            elif self.active_handle == 'rc': rect.setRight(mouse_pos.x())
            elif self.active_handle == 'bl': rect.setBottomLeft(mouse_pos)
            elif self.active_handle == 'bc': rect.setBottom(mouse_pos.y())
            elif self.active_handle == 'br': rect.setBottomRight(mouse_pos)

            if rect.width() > 10 and rect.height() > 10:
                self.setRect(rect)
                self.update_handles_positions()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if hasattr(self.scene(), 'clear_guides'): self.scene().clear_guides()

        if self.resizing or self.start_pos != self.pos():
            if hasattr(self.scene(), 'main_window'):
                mw = self.scene().main_window
                cmd = ModifyFieldCommand(self, self.start_rect, self.start_pos, self.rect(), self.pos())
                mw.undo_stack.push(cmd)

        self.resizing = False
        self.active_handle = None
        super().mouseReleaseEvent(event)


# ================= VISTA Y MANEJO DE ESCENA =================

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
                if line.scene(): self.removeItem(line)
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
        
        # Ahora el zoom con la rueda del ratón o atajos siempre se centra donde esté el cursor!
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
            step = 1 if not (event.modifiers() & Qt.ShiftModifier) else 10
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
            if event.angleDelta().y() > 0: self.main_window.zoom_in()
            else: self.main_window.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        if hasattr(self, 'main_window'):
            self.main_window.update_page_label()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and event.mimeData().urls()[0].toLocalFile().lower().endswith('.pdf'):
            event.accept()
        else: super().dragEnterEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile() and urls[0].toLocalFile().lower().endswith('.pdf'):
            self.main_window.load_pdf(urls[0].toLocalFile())
            event.accept()
        else: super().dropEvent(event)


# ================= CONTENEDOR PRINCIPAL Y UI MODERNA =================

class PDFFormEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        
        app_font = QFont("Segoe UI", 10)
        app_font.setStyleHint(QFont.SansSerif)
        QApplication.instance().setFont(app_font)

        self.setWindowTitle("PDFormer - Editor de Formularios PDF")
        self.setGeometry(100, 100, 1280, 800)
        self.setAcceptDrops(True)
        self.setStyleSheet("QMainWindow { background-color: #f8f9fc; font-family: 'Segoe UI', 'Helvetica Neue', sans-serif; }")

        self.current_file_path = None
        self.doc = None
        self.current_page = 0
        self.zoom = 1.0  
        self.current_tool = None
        self.snap_enabled = True
        
        self.undo_stack = QUndoStack(self)
        self.all_fields = set() 
        self.page_rects = {} 
        self.copied_field_data = None
        
        self.sidebar_buttons = {}

        self.setup_ui()
        self.setup_actions()
        
        self.close_document()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. HEADER
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet("background-color: white; border-bottom: 1px solid #e2e8f0;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        
        # Logo y Título
        logo_layout = QHBoxLayout()
        logo_icon = QLabel()
        logo_icon.setPixmap(qta.icon('fa5s.file-pdf', color='white').pixmap(20, 20))
        logo_icon.setStyleSheet("background-color: #0b50da; border-radius: 8px; padding: 6px;")
        
        title = QLabel("PDFormer")
        title.setStyleSheet("font-weight: bold; font-size: 18px; color: #0f172a; border: none;")
        logo_layout.addWidget(logo_icon)
        logo_layout.addWidget(title)
        
        nav_layout = QHBoxLayout()
        self.btn_file = self.create_nav_button("Archivo")
        self.btn_edit = self.create_nav_button("Edición")
        self.btn_pages = self.create_nav_button("Páginas")
        nav_layout.addWidget(self.btn_file)
        nav_layout.addWidget(self.btn_edit)
        nav_layout.addWidget(self.btn_pages)
        
        left_header = QHBoxLayout()
        left_header.addLayout(logo_layout)
        left_header.addSpacing(20)
        left_header.addLayout(nav_layout)
        header_layout.addLayout(left_header)
        header_layout.addStretch()

        right_header = QHBoxLayout()
        
        ur_container = QWidget()
        ur_container.setStyleSheet("background-color: #f1f5f9; border-radius: 8px;")
        ur_layout = QHBoxLayout(ur_container)
        ur_layout.setContentsMargins(4, 4, 4, 4)
        ur_layout.setSpacing(2)
        
        # Iconos QtAwesome para la cabecera
        self.btn_undo = self.create_icon_btn("fa5s.undo-alt", "Deshacer")
        self.btn_redo = self.create_icon_btn("fa5s.redo-alt", "Rehacer")
        ur_layout.addWidget(self.btn_undo)
        ur_layout.addWidget(self.btn_redo)
        
        divider1 = QFrame()
        divider1.setFrameShape(QFrame.VLine)
        divider1.setStyleSheet("color: #e2e8f0; margin: 0 4px;")
        
        self.btn_copy = self.create_icon_btn("fa5s.copy", "Copiar")
        self.btn_paste = self.create_icon_btn("fa5s.paste", "Pegar")
        self.btn_delete = self.create_icon_btn("fa5s.trash-alt", "Eliminar", color="#ef4444", hover_color="#dc2626")
        self.btn_delete.setStyleSheet("QPushButton { background: transparent; border-radius: 6px; border: none; } QPushButton:hover { background: #fef2f2; }")
        
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.VLine)
        divider2.setStyleSheet("color: #e2e8f0; margin: 0 4px;")
        
        self.btn_add_page = QPushButton(" Añadir Página")
        self.btn_add_page.setIcon(qta.icon('fa5s.plus-circle', color='white'))
        self.btn_add_page.setStyleSheet("""
            QPushButton { background-color: #0b50da; color: white; border-radius: 8px; padding: 6px 14px; font-weight: bold; font-size: 13px; border: none; }
            QPushButton:hover { background-color: #0940b0; }
        """)
        
        right_header.addWidget(ur_container)
        right_header.addWidget(divider1)
        right_header.addWidget(self.btn_copy)
        right_header.addWidget(self.btn_paste)
        right_header.addWidget(self.btn_delete)
        right_header.addWidget(divider2)
        right_header.addWidget(self.btn_add_page)
        header_layout.addLayout(right_header)

        # 2. ÁREA CENTRAL
        middle_widget = QWidget()
        middle_layout = QHBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)

        # SIDEBAR CON ICONOS QTAWESOME
        sidebar = QWidget()
        sidebar.setFixedWidth(256)
        sidebar.setStyleSheet("background-color: #f8f9fc; border-right: 1px solid #e2e8f0;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(4)
        
        self.add_sidebar_section(sidebar_layout, "HERRAMIENTAS DE EDICIÓN")
        self.add_sidebar_tool(sidebar_layout, 'cursor', "fa5s.mouse-pointer", "Cursor")
        self.add_sidebar_tool(sidebar_layout, 'snap', "fa5s.magic", "Guías Magnéticas", is_toggle=True)
        
        self.add_sidebar_divider(sidebar_layout)
        
        self.add_sidebar_section(sidebar_layout, "ANOTACIÓN")
        self.add_sidebar_tool(sidebar_layout, 'static_text', "fa5s.font", "Texto Libre")
        self.add_sidebar_tool(sidebar_layout, 'whiteout', "fa5s.eraser", "Típex")
        
        self.add_sidebar_divider(sidebar_layout)
        
        self.add_sidebar_section(sidebar_layout, "ELEMENTOS DE FORMULARIO")
        self.add_sidebar_tool(sidebar_layout, 'text', "fa5s.text-height", "Texto")
        self.add_sidebar_tool(sidebar_layout, 'textarea', "fa5s.align-left", "Texto Multilínea")
        self.add_sidebar_tool(sidebar_layout, 'checkbox', "fa5s.check-square", "Checkbox")
        self.add_sidebar_tool(sidebar_layout, 'dropdown', "fa5s.caret-square-down", "Desplegable")
        self.add_sidebar_tool(sidebar_layout, 'signature', "fa5s.pen-nib", "Firma")
        
        sidebar_layout.addStretch()

        workspace_container = QWidget()
        workspace_layout = QGridLayout(workspace_container)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        
        self.viewer = PDFViewer(self)
        workspace_layout.addWidget(self.viewer, 0, 0)
        
        self.setup_welcome_screen(workspace_layout)
        
        # Controles Flotantes
        self.floating_container = QWidget()
        self.floating_container.setStyleSheet("background: transparent;")
        floating_layout = QVBoxLayout(self.floating_container)
        floating_layout.setContentsMargins(0, 0, 24, 24)
        floating_layout.setSpacing(12)
        
        self.btn_fit_width = self.create_floating_btn("fa5s.arrows-alt-h", "Ajustar al ancho")
        self.btn_zoom_in = self.create_floating_btn("fa5s.search-plus", "Ampliar")
        self.btn_zoom_out = self.create_floating_btn("fa5s.search-minus", "Reducir")
        
        floating_layout.addWidget(self.btn_fit_width)
        floating_layout.addWidget(self.btn_zoom_in)
        floating_layout.addWidget(self.btn_zoom_out)
        
        workspace_layout.addWidget(self.floating_container, 0, 0, Qt.AlignBottom | Qt.AlignRight)

        middle_layout.addWidget(sidebar)
        middle_layout.addWidget(workspace_container)

        # 3. FOOTER
        footer = QWidget()
        footer.setFixedHeight(40)
        footer.setStyleSheet("background-color: white; border-top: 1px solid #e2e8f0;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)

        self.status_label = QLabel("✨ Bienvenido a PDFormer. Abre un documento PDF para empezar.")
        self.status_label.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500; border: none;")
        
        nav_controls = QHBoxLayout()
        self.btn_prev = self.create_icon_btn("fa5s.chevron-left", "Anterior")
        self.page_label = QLabel(" Página 0 / 0 ")
        self.page_label.setStyleSheet("background-color: #f1f5f9; color: #334155; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px;")
        self.btn_next = self.create_icon_btn("fa5s.chevron-right", "Siguiente")
        
        divider3 = QFrame()
        divider3.setFrameShape(QFrame.VLine)
        divider3.setStyleSheet("color: #e2e8f0; margin: 0 8px;")
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #475569; border: none;")

        nav_controls.addWidget(self.btn_prev)
        nav_controls.addWidget(self.page_label)
        nav_controls.addWidget(self.btn_next)
        nav_controls.addWidget(divider3)
        nav_controls.addWidget(QLabel("ZOOM", styleSheet="color: #94a3b8; font-size: 10px; font-weight: bold; border: none; padding-right: 4px;"))
        nav_controls.addWidget(self.zoom_label)

        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()
        footer_layout.addLayout(nav_controls)

        main_layout.addWidget(header)
        main_layout.addWidget(middle_widget)
        main_layout.addWidget(footer)

        self.set_tool('cursor')

    def setup_welcome_screen(self, layout):
        self.welcome_widget = QWidget()
        self.welcome_widget.setStyleSheet("background-color: #f8f9fc;")
        
        vbox = QVBoxLayout(self.welcome_widget)
        vbox.addStretch()
        
        # Contenedor central
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)
        
        # Icono subida
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon('fa5s.file-upload', color='#94a3b8').pixmap(64, 64))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background-color: #f1f5f9; border-radius: 40px; padding: 20px;")
        icon_lbl.setFixedSize(100, 100)
        
        icon_container = QHBoxLayout()
        icon_container.addStretch()
        icon_container.addWidget(icon_lbl)
        icon_container.addStretch()
        
        # Textos
        title = QLabel("Ningún documento abierto")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #0f172a; margin-top: 20px;")
        title.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("Bienvenido a PDFormer. Arrastra y suelta un documento PDF aquí\no usa los botones para empezar a editar, anotar y firmar.")
        subtitle.setStyleSheet("font-size: 14px; color: #64748b; margin-top: 10px; margin-bottom: 30px;")
        subtitle.setAlignment(Qt.AlignCenter)
        
        # Botones
        btns_layout = QHBoxLayout()
        btns_layout.addStretch()
        
        btn_open = QPushButton("Abrir PDF")
        btn_open.setStyleSheet("""
            QPushButton { background-color: #0b50da; color: white; border-radius: 20px; padding: 10px 24px; font-weight: bold; font-size: 14px; border: none; }
            QPushButton:hover { background-color: #0940b0; }
        """)
        btn_open.clicked.connect(self.open_pdf)
        
        btn_new = QPushButton("Nuevo en blanco")
        btn_new.setStyleSheet("""
            QPushButton { background-color: #f1f5f9; color: #334155; border-radius: 20px; padding: 10px 24px; font-weight: bold; font-size: 14px; border: none; }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_new.clicked.connect(self.new_pdf)
        
        btns_layout.addWidget(btn_open)
        btns_layout.addSpacing(15)
        btns_layout.addWidget(btn_new)
        btns_layout.addStretch()
        
        center_layout.addLayout(icon_container)
        center_layout.addWidget(title)
        center_layout.addWidget(subtitle)
        center_layout.addLayout(btns_layout)
        
        vbox.addWidget(center_widget)
        vbox.addStretch()
        
        layout.addWidget(self.welcome_widget, 0, 0)

    def update_ui_state(self):
        if self.doc is not None and len(self.doc) > 0:
            self.welcome_widget.hide()
            self.viewer.show()
            self.floating_container.show()
        else:
            self.viewer.hide()
            self.floating_container.hide()
            self.welcome_widget.show()

    def close_document(self):
        if self.doc and not self.undo_stack.isClean():
            if QMessageBox.question(self, "Aviso", "Hay cambios sin guardar. ¿Descartar y cerrar?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No: return
        if self.doc:
            self.doc.close()
            self.doc = None
        self.current_file_path = None
        self.current_page = 0
        self.all_fields.clear()
        self.undo_stack.clear()
        self.viewer.scene.clear()
        self.zoom = 1.0
        self.viewer.setTransform(QTransform()) # Reseteamos la cámara visual
        self.zoom_label.setText("100%")
        self.setWindowTitle("PDFormer")
        self.status_label.setText("✨ Bienvenido a PDFormer. Abre un documento PDF para empezar.")
        self.update_ui_state()
        self.update_page_label()

    def create_nav_button(self, text):
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton { background: transparent; color: #475569; font-weight: 500; font-size: 14px; padding: 6px 12px; border-radius: 6px; border: none; }
            QPushButton::menu-indicator { image: none; }
            QPushButton:hover { background: #f1f5f9; color: #0f172a; }
        """)
        return btn

    def create_icon_btn(self, icon_name, tooltip, color="#64748b", hover_color="#0b50da"):
        btn = QPushButton()
        btn.setToolTip(tooltip)
        btn.setFixedSize(32, 32)
        btn.setIcon(qta.icon(icon_name, color=color, color_active=hover_color))
        btn.setIconSize(QSize(18, 18))
        btn.setStyleSheet("""
            QPushButton { background: transparent; border-radius: 6px; border: none; }
            QPushButton:hover { background: #e2e8f0; }
        """)
        return btn

    def create_floating_btn(self, icon_name, tooltip):
        btn = QPushButton()
        btn.setToolTip(tooltip)
        btn.setFixedSize(48, 48)
        btn.setIcon(qta.icon(icon_name, color="#475569", color_active="#0b50da"))
        btn.setIconSize(QSize(20, 20))
        btn.setStyleSheet("""
            QPushButton {
                background: white;
                border-radius: 24px;
                border: 1px solid #e2e8f0;
            }
            QPushButton:hover {
                background: #f8f9fc;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 4)
        btn.setGraphicsEffect(shadow)
        return btn

    def add_sidebar_section(self, layout, title):
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; letter-spacing: 1px; padding-left: 8px; margin-top: 12px; border: none;")
        layout.addWidget(lbl)

    def add_sidebar_divider(self, layout):
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #e2e8f0; margin: 8px 0;")
        layout.addWidget(div)

    def add_sidebar_tool(self, layout, tool_id, icon_name, text, is_toggle=False):
        btn = QPushButton(f"  {text}")
        btn.setCheckable(is_toggle)
        btn.setProperty('tool_id', tool_id)
        btn.setProperty('active', False)
        btn.setProperty('icon_name', icon_name)
        
        btn.setIcon(qta.icon(icon_name, color="#475569"))
        btn.setIconSize(QSize(18, 18))
        
        style = """
            QPushButton { 
                text-align: left; 
                padding: 10px 14px; 
                border-radius: 8px; 
                background: transparent; 
                color: #475569; 
                font-weight: 500; 
                font-size: 14px; 
                border: none; 
            }
            QPushButton:hover { background: #e2e8f0; color: #0f172a; }
            QPushButton[active="true"] { background: #0b50da; color: white; font-weight: bold; }
        """
        btn.setStyleSheet(style)
        
        if tool_id == 'snap':
            btn.setChecked(True)
            btn.setProperty('active', True)
            btn.setIcon(qta.icon(icon_name, color="#ffffff"))
            btn.clicked.connect(self.toggle_snap)
        else:
            btn.clicked.connect(lambda checked, tid=tool_id: self.set_tool(tid))
            
        layout.addWidget(btn)
        self.sidebar_buttons[tool_id] = btn

    def setup_actions(self):
        menu_file = QMenu(self)
        menu_file.setStyleSheet("QMenu { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px; font-family: 'Segoe UI'; } QMenu::item { padding: 8px 24px; color: #0f172a; } QMenu::item:selected { background: #eff6ff; color: #0b50da; }")
        menu_file.addAction(qta.icon('fa5s.file-alt', color='#0f172a'), "Nuevo PDF (Ctrl+N)", self.new_pdf, "Ctrl+N")
        menu_file.addAction(qta.icon('fa5s.folder-open', color='#0f172a'), "Abrir PDF (Ctrl+O)", self.open_pdf, "Ctrl+O")
        menu_file.addAction(qta.icon('fa5s.save', color='#0f172a'), "Guardar (Ctrl+S)", self.save_pdf, "Ctrl+S")
        menu_file.addAction(qta.icon('fa5s.download', color='#0f172a'), "Guardar como...", self.save_pdf_as, "Ctrl+Shift+S")
        menu_file.addSeparator()
        menu_file.addAction(qta.icon('fa5s.times-circle', color='#0f172a'), "Salir (Ctrl+Q)", self.close, "Ctrl+Q")
        self.btn_file.setMenu(menu_file)

        menu_edit = QMenu(self)
        menu_edit.setStyleSheet(menu_file.styleSheet())
        menu_edit.addAction(qta.icon('fa5s.undo-alt', color='#0f172a'), "Deshacer", self.undo_stack.undo, "Ctrl+Z")
        menu_edit.addAction(qta.icon('fa5s.redo-alt', color='#0f172a'), "Rehacer", self.undo_stack.redo, "Ctrl+Y")
        menu_edit.addSeparator()
        menu_edit.addAction(qta.icon('fa5s.copy', color='#0f172a'), "Copiar", self.copy_field, "Ctrl+C")
        menu_edit.addAction(qta.icon('fa5s.paste', color='#0f172a'), "Pegar", self.paste_field, "Ctrl+V")
        menu_edit.addAction(qta.icon('fa5s.trash-alt', color='#ef4444'), "Eliminar", self.delete_selected_field, "Del")
        self.btn_edit.setMenu(menu_edit)

        menu_pages = QMenu(self)
        menu_pages.setStyleSheet(menu_file.styleSheet())
        menu_pages.addAction(qta.icon('fa5s.plus', color='#0f172a'), "Añadir Página", self.add_blank_page)
        menu_pages.addAction(qta.icon('fa5s.trash', color='#ef4444'), "Borrar Página", self.delete_current_page)
        self.btn_pages.setMenu(menu_pages)

        self.btn_undo.clicked.connect(self.undo_stack.undo)
        self.btn_redo.clicked.connect(self.undo_stack.redo)
        self.btn_copy.clicked.connect(self.copy_field)
        self.btn_paste.clicked.connect(self.paste_field)
        self.btn_delete.clicked.connect(self.delete_selected_field)
        self.btn_add_page.clicked.connect(self.add_blank_page)

        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next.clicked.connect(self.next_page)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_fit_width.clicked.connect(self.fit_to_width)

        self.btn_undo.setEnabled(False)
        self.btn_redo.setEnabled(False)
        self.undo_stack.canUndoChanged.connect(self.btn_undo.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.btn_redo.setEnabled)

    def toggle_snap(self, checked):
        self.snap_enabled = checked
        btn = self.sidebar_buttons['snap']
        btn.setProperty('active', checked)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        
        # Actualizar color del icono dinámicamente
        color = "#ffffff" if checked else "#475569"
        btn.setIcon(qta.icon(btn.property('icon_name'), color=color))
        
        estado = "activadas" if checked else "desactivadas"
        self.status_label.setText(f"✦ Guías magnéticas {estado}.")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and event.mimeData().urls()[0].toLocalFile().lower().endswith('.pdf'):
            event.accept()
        else: super().dragEnterEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile() and urls[0].toLocalFile().lower().endswith('.pdf'):
            self.load_pdf(urls[0].toLocalFile())
            event.accept()
        else: super().dropEvent(event)

    def set_tool(self, tool_id):
        if tool_id == 'cursor':
            self.current_tool = None
            self.viewer.setCursor(Qt.ArrowCursor)
            self.status_label.setText("Modo Cursor. Selecciona o redimensiona.")
        else:
            self.current_tool = tool_id
            self.viewer.setCursor(Qt.CrossCursor)
            self.viewer.scene.clearSelection()
            
            nombres_herramientas = {
                'static_text': 'Texto Libre', 'whiteout': 'Típex',
                'text': 'Texto', 'textarea': 'Texto Multilínea',
                'checkbox': 'Checkbox', 'dropdown': 'Desplegable',
                'signature': 'Firma'
            }
            nombre_modo = nombres_herramientas.get(tool_id, tool_id.capitalize())
            self.status_label.setText(f"✏️ Modo {nombre_modo} activo. Haz clic y arrastra en el PDF.")

        for tid, btn in self.sidebar_buttons.items():
            if tid == 'snap': continue 
            
            is_active = (tid == tool_id)
            btn.setProperty('active', is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            
            # Repintar el icono para que se vuelva blanco sobre el fondo azul
            color = "#ffffff" if is_active else "#475569"
            btn.setIcon(qta.icon(btn.property('icon_name'), color=color))

    def new_pdf(self):
        if self.doc and not self.undo_stack.isClean():
            if QMessageBox.question(self, "Aviso", "Hay cambios sin guardar. ¿Descartar?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No: return
        
        self.current_file_path = None
        self.doc = fitz.open()
        self.doc.new_page(width=595, height=842)
        self.current_page = 0
        self.all_fields.clear()
        self.undo_stack.clear()
        
        # Ahora reseteamos visualmente la cámara, pero NO las matemáticas del dibujo
        self.zoom = 1.0
        self.viewer.setTransform(QTransform())
        
        self.render_document()
        self.update_page_label()
        self.update_ui_state()
        self.status_label.setText("📄 Nuevo documento en blanco creado.")
        self.setWindowTitle("PDFormer - Sin Título")

    def open_pdf(self):
        if self.doc and not self.undo_stack.isClean():
            if QMessageBox.question(self, "Aviso", "¿Descartar cambios actuales?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No: return
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "PDF (*.pdf)")
        if file_path: self.load_pdf(file_path)

    def load_pdf(self, file_path):
        try:
            with open(file_path, "rb") as f: pdf_data = f.read()
            self.doc = fitz.open("pdf", pdf_data)
            self.current_file_path = file_path
            self.current_page = 0
            self.all_fields.clear()
            self.undo_stack.clear()
            
            self.zoom = 1.0
            self.viewer.setTransform(QTransform())
            
            self.render_document()
            self.update_page_label()
            self.update_ui_state()
            self.status_label.setText(f"📄 Documento abierto: {file_path}")
            self.setWindowTitle(f"PDFormer - {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir:\n{str(e)}")

    def zoom_in(self):
        self.zoom = min(self.zoom * 1.15, 3.0)
        # Hacemos zoom en la vista de la cámara, sin tocar los píxeles internos ni redibujar todo
        self.viewer.setTransform(QTransform().scale(self.zoom, self.zoom))
        self.zoom_label.setText(f"{int(self.zoom * 100)}%")

    def zoom_out(self):
        self.zoom = max(self.zoom / 1.15, 0.5)
        self.viewer.setTransform(QTransform().scale(self.zoom, self.zoom))
        self.zoom_label.setText(f"{int(self.zoom * 100)}%")

    def fit_to_width(self):
        if not self.doc or len(self.doc) == 0: return
        max_w = max(page.rect.width for page in self.doc)
        view_w = self.viewer.viewport().width() - 40 # 40px de margen
        self.zoom = max(0.5, min(view_w / max_w, 3.0)) # Limitamos entre 0.5x y 3x
        
        self.viewer.setTransform(QTransform().scale(self.zoom, self.zoom))
        self.zoom_label.setText(f"{int(self.zoom * 100)}%")

    def add_blank_page(self):
        if not self.doc: return self.new_pdf()
        w, h = self.doc[self.current_page].rect.width, self.doc[self.current_page].rect.height
        new_idx = self.current_page + 1
        self.doc.new_page(pno=new_idx, width=w, height=h)
        
        # Como las coordenadas internas ya no se escalan con el zoom, shift es simple
        shift_amount = h + 30
        boundary_y = self.page_rects[self.current_page].bottom()
        for item in self.all_fields:
            try:
                if item.sceneBoundingRect().center().y() > boundary_y:
                    item.setPos(item.x(), item.y() + shift_amount)
            except RuntimeError: pass
                
        self.current_page = new_idx
        self.render_document()
        if new_idx in self.page_rects: self.viewer.verticalScrollBar().setValue(int(self.page_rects[new_idx].top()))
        self.update_page_label()

    def delete_current_page(self):
        if not self.doc or len(self.doc) == 0: return
        if len(self.doc) == 1: 
            if QMessageBox.question(self, "Aviso", "¿Eliminar la única página? Esto cerrará el documento.", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                self.close_document()
            return
            
        if QMessageBox.question(self, "Aviso", "¿Borrar página actual y sus elementos?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.No: return
        
        p_rect = self.page_rects[self.current_page]
        shift_amount = p_rect.height() + 30
        items_to_remove = []
        for item in self.all_fields:
            try:
                cy = item.sceneBoundingRect().center().y()
                if p_rect.top() <= cy <= p_rect.bottom(): items_to_remove.append(item)
                elif cy > p_rect.bottom(): item.setPos(item.x(), item.y() - shift_amount)
            except RuntimeError: pass
                
        for item in items_to_remove:
            try:
                if item.scene() == self.viewer.scene: self.viewer.scene.removeItem(item)
                self.all_fields.discard(item)
            except RuntimeError: pass
            
        self.doc.delete_page(self.current_page)
        if self.current_page >= len(self.doc): self.current_page = len(self.doc) - 1
        self.render_document()
        self.update_page_label()

    def create_field(self, scene_rect):
        timestamp = int(time.time() * 1000)
        name = f"Campo_{timestamp}"
        options, text_content = None, ""
        has_border = self.current_tool not in ['static_text', 'whiteout']

        if self.current_tool == 'dropdown':
            text, ok = QInputDialog.getText(self, "Opciones", "Separadas por coma:")
            if ok and text.strip(): options = [o.strip() for o in text.split(',') if o.strip()]
            else: return
        elif self.current_tool == 'static_text':
            text, ok = QInputDialog.getMultiLineText(self, "Texto", "Escribe:")
            if ok and text.strip(): text_content = text.strip()
            else: return

        item = FieldItem(scene_rect, self.current_tool, name, options, has_border, text_content)
        self.undo_stack.push(AddFieldCommand(self.viewer.scene, item, self.all_fields))
        
        self.set_tool('cursor')

    def delete_selected_field(self):
        for item in self.viewer.scene.selectedItems():
            if isinstance(item, FieldItem): self.undo_stack.push(RemoveFieldCommand(self.viewer.scene, item, self.all_fields))

    def copy_field(self):
        items = self.viewer.scene.selectedItems()
        if items and isinstance(items[0], FieldItem):
            item = items[0]
            try:
                self.copied_field_data = {'type': item.field_type, 'rect': item.rect(), 'options': item.options, 'has_border': item.has_border, 'text_content': item.text_content}
                self.status_label.setText("✅ Elemento copiado.")
            except RuntimeError: pass

    def paste_field(self):
        if not self.copied_field_data: return
        data = self.copied_field_data
        item = FieldItem(data['rect'].translated(20, 20), data['type'], f"Copiado_{int(time.time()*1000)}", data['options'], data.get('has_border', True), data.get('text_content', ""))
        self.undo_stack.push(AddFieldCommand(self.viewer.scene, item, self.all_fields))

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.viewer.verticalScrollBar().setValue(int(self.page_rects[self.current_page].top()))
            self.update_page_label()

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.viewer.verticalScrollBar().setValue(int(self.page_rects[self.current_page].top()))
            self.update_page_label()

    def update_page_label(self):
        if not self.doc or not self.page_rects: 
            self.page_label.setText(" Página 0 / 0 ")
            return
        view_center_y = self.viewer.mapToScene(self.viewer.viewport().rect().center()).y()
        for p_num, p_rect in self.page_rects.items():
            if p_rect.top() <= view_center_y <= p_rect.bottom() + 30:
                self.current_page = p_num
                break
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < len(self.doc) - 1)
        self.page_label.setText(f" Página {self.current_page + 1} / {len(self.doc)} ")

    def render_document(self):
        if not self.doc: return
        
        # Eliminamos la limpieza chapucera, dejamos los elementos en paz
        for item in list(self.viewer.scene.items()):
            try:
                if item.parentItem() is None and not isinstance(item, FieldItem): 
                    self.viewer.scene.removeItem(item)
            except RuntimeError: pass
                
        self.viewer.scene.guide_lines.clear()
        self.page_rects.clear()
        
        current_y = 0
        gap = 30 
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            
            # Generamos la imagen con 2X de resolución siempre para que al acercarse se vea nítido
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, annots=True)
            
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            
            bg_item = self.viewer.scene.addPixmap(pixmap)
            
            # Lo reducimos al tamaño 1:1 real del PDF interno, pero conservando la calidad visual
            bg_item.setScale(0.5)
            bg_item.setPos(0, current_y)
            bg_item.setZValue(-1) 
            
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(20)
            shadow.setXOffset(0)
            shadow.setYOffset(4)
            shadow.setColor(QColor(0, 0, 0, 30))
            bg_item.setGraphicsEffect(shadow)
            
            # ¡CLAVE! Guardamos la caja al tamaño natural del PDF, no influenciada por pixmap ni zooms visuales
            self.page_rects[page_num] = QRectF(0, current_y, page.rect.width, page.rect.height)
            current_y += page.rect.height + gap

        if self.page_rects: self.viewer.setSceneRect(self.viewer.scene.itemsBoundingRect())
        
        # Como no borramos los Fields de la escena, no hace falta readjuntarlos. Solo garantizamos que se vean.
        for item in self.all_fields:
            try:
                if item.scene() is None: self.viewer.scene.addItem(item)
                item.show()
            except RuntimeError: pass

    def save_pdf(self):
        if not self.doc: return False
        return self._perform_save(self.current_file_path) if self.current_file_path else self.save_pdf_as()
            
    def save_pdf_as(self):
        if not self.doc: return False
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar como...", "", "PDF (*.pdf)")
        if file_path and self._perform_save(file_path):
            self.current_file_path = file_path
            self.setWindowTitle(f"PDFormer - {file_path}")
            return True
        return False

    def _perform_save(self, file_path):
        try:
            pdf_bytes = self.doc.write()
            export_doc = fitz.open("pdf", pdf_bytes)

            try:
                export_doc.set_xml_metadata("")
                export_doc.set_metadata({}) 
                catalog_xref = export_doc.pdf_catalog()
                export_doc.xref_set_key(catalog_xref, "OutputIntents", "null")
                export_doc.xref_set_key(catalog_xref, "Metadata", "null")
            except Exception: pass

            for item in self.all_fields:
                try:
                    if item.scene() is None: continue 
                    item_center_y = item.sceneBoundingRect().center().y()
                    final_rect = item.sceneBoundingRect()
                except RuntimeError: continue 
                
                target_page = 0
                for p_num, p_rect in self.page_rects.items():
                    if p_rect.top() <= item_center_y <= p_rect.bottom() + 30:
                        target_page = p_num
                        break
                
                page = export_doc[target_page]
                p_rect = self.page_rects[target_page]
                
                # Como la escena ahora funciona 1:1, podemos calcular las coordenadas con simple resta, sin dividir por el zoom
                x0 = final_rect.left() - p_rect.left()
                y0 = final_rect.top() - p_rect.top()
                x1 = final_rect.right() - p_rect.left()
                y1 = final_rect.bottom() - p_rect.top()
                fitz_rect = fitz.Rect(x0, y0, x1, y1)

                if item.field_type == 'whiteout':
                    page.draw_rect(fitz_rect, color=(1,1,1), fill=(1,1,1))
                    if item.has_border: page.draw_rect(fitz_rect, color=(0,0,0), fill=None, width=1)
                elif item.field_type == 'static_text':
                    if item.has_border: page.draw_rect(fitz_rect, color=(0,0,0), fill=None, width=1)
                    page.insert_textbox(fitz_rect, item.text_content, fontsize=11, fontname="helv", color=(0,0,0), align=0)
                else:
                    widget = fitz.Widget()
                    widget.rect = fitz_rect
                    if item.field_type != 'signature': widget.fill_color = (0.85, 0.9, 1.0)
                    
                    if item.has_border:
                        widget.border_color = (0, 0, 0)
                        widget.border_width = 1
                    else: widget.border_width = 0

                    if item.field_type == 'text':
                        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                        widget.field_name = item.field_name
                    elif item.field_type == 'textarea':
                        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                        widget.field_name = item.field_name
                        widget.field_flags |= 4096 
                        widget.text_fontsize = 0
                    elif item.field_type == 'checkbox':
                        widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                        widget.field_name = item.field_name
                    elif item.field_type == 'dropdown':
                        widget.field_type = fitz.PDF_WIDGET_TYPE_COMBOBOX
                        widget.field_name = item.field_name
                        widget.choice_values = item.options
                    elif item.field_type == 'signature':
                        widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
                        widget.field_name = item.field_name

                    new_widget = page.add_widget(widget)
                    if item.field_type == 'signature':
                        xref = getattr(widget, 'xref', None) or (getattr(new_widget, 'xref', None) if new_widget else None)
                        if not xref:
                            annot = page.first_widget
                            while annot:
                                if getattr(annot, 'field_name', '') == item.field_name:
                                    xref = annot.xref
                                    break
                                annot = annot.next
                        if xref: export_doc.xref_set_key(xref, "Lock", "<< /Action /All >>")

            export_doc.save(file_path, deflate=True, garbage=4, clean=True)
            export_doc.close()
            self.undo_stack.setClean()
            self.status_label.setText("✅ Guardado con éxito.")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al guardar:\n{str(e)}")
            return False

    def closeEvent(self, event):
        if self.doc and not self.undo_stack.isClean():
            msg = QMessageBox(self)
            msg.setWindowTitle("Documento sin guardar")
            msg.setText("Hay cambios sin guardar. ¿Cerrar?")
            btn_save = msg.addButton("Guardar", QMessageBox.AcceptRole)
            btn_yes = msg.addButton("Sí", QMessageBox.DestructiveRole)
            msg.addButton("No", QMessageBox.RejectRole)
            msg.exec_()
            if msg.clickedButton() == btn_save and self.save_pdf(): event.accept()
            elif msg.clickedButton() == btn_yes: event.accept()
            else: event.ignore()
        else: event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = PDFFormEditor()
    editor.show()
    sys.exit(app.exec_())