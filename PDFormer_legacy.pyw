import sys
import subprocess

# --- AUTO-INSTALADOR DE DEPENDENCIAS ---
def check_and_install_dependencies():
    required = {'fitz': 'PyMuPDF', 'PyQt5': 'PyQt5'}
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
import time
import copy
import fitz  # PyMuPDF
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QGraphicsView, 
                             QGraphicsScene, QAction, QToolBar, QMessageBox, QInputDialog, 
                             QRubberBand, QLabel, QGraphicsRectItem, QGraphicsItem, 
                             QGraphicsDropShadowEffect, QUndoStack, QUndoCommand, QMenuBar, QMenu,
                             QWidget, QHBoxLayout, QToolButton)
from PyQt5.QtGui import QImage, QPixmap, QCursor, QColor, QBrush, QPen, QKeySequence, QFont
from PyQt5.QtCore import Qt, QRect, QPoint, QPointF, QRectF, QSizeF

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
            # Actualizar los manejadores visuales si el tamaño cambió por código
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
    """ Puntos para redimensionar el campo (Material Style) """
    def __init__(self, position_type, parent):
        super().__init__(-5, -5, 10, 10, parent)
        self.position_type = position_type
        self.setBrush(QBrush(QColor("#6750A4"))) 
        self.setPen(QPen(QColor("#FFFFFF"), 1.5))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        
        if position_type in ['tl', 'br']:
            self.setCursor(Qt.SizeFDiagCursor)
        elif position_type in ['tr', 'bl']:
            self.setCursor(Qt.SizeBDiagCursor)
        elif position_type in ['tc', 'bc']:
            self.setCursor(Qt.SizeVerCursor)
        elif position_type in ['lc', 'rc']:
            self.setCursor(Qt.SizeHorCursor)

class FieldItem(QGraphicsRectItem):
    """ Representa un campo o elemento que flota sobre el PDF """
    def __init__(self, rect, field_type, field_name, options=None, has_border=True, text_content=""):
        super().__init__(rect)
        self.field_type = field_type
        self.field_name = field_name
        self.options = options
        self.has_border = has_border
        self.text_content = text_content
        self.main_window = None 

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
        if self.field_type == 'whiteout':
            self.setBrush(QBrush(QColor(255, 255, 255, 255))) 
            if self.has_border:
                self.setPen(QPen(QColor("#21005D"), 1.5))
            else:
                self.setPen(QPen(QColor(150, 150, 150, 150), 1, Qt.DashLine)) 
        elif self.field_type == 'static_text':
            self.setBrush(QBrush(QColor(255, 255, 255, 1))) 
            if self.has_border:
                self.setPen(QPen(QColor("#21005D"), 1.5))
            else:
                self.setPen(QPen(QColor(150, 150, 150, 150), 1, Qt.DashLine)) 
        elif self.field_type == 'signature':
            self.setBrush(QBrush(QColor(255, 235, 156, 160))) 
            if self.has_border:
                self.setPen(QPen(QColor("#21005D"), 1.5))
            else:
                self.setPen(QPen(Qt.NoPen))
        else:
            self.setBrush(QBrush(QColor(234, 221, 255, 160))) 
            if self.has_border:
                self.setPen(QPen(QColor("#21005D"), 1.5))
            else:
                self.setPen(QPen(Qt.NoPen))

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.field_type == 'static_text' and self.text_content:
            painter.setPen(QPen(Qt.black))
            font = QFont("Segoe UI", 11)
            painter.setFont(font)
            painter.drawText(self.rect().adjusted(4, 4, -4, -4), Qt.TextWordWrap | Qt.AlignTop | Qt.AlignLeft, self.text_content)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #FEF7FF; border: 1px solid #CAC4D0; border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 8px 24px; border-radius: 4px; }
            QMenu::item:selected { background-color: #EADDFF; color: #21005D; }
        """)
        action_text = "🚫 Quitar borde" if self.has_border else "🔲 Poner borde"
        toggle_action = menu.addAction(action_text)
        
        edit_text_action = None
        if self.field_type == 'static_text':
            edit_text_action = menu.addAction("✏️ Editar Texto")
            
        resize_action = menu.addAction("📏 Definir tamaño...")
        
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
                dialog.setStyleSheet("QInputDialog { background-color: #FEF7FF; } QLineEdit { padding: 6px; border: 1px solid #CAC4D0; border-radius: 4px; }")
                
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
                
            # Si el imán está desactivado, moverse libremente
            if mw and not mw.action_toggle_snap.isChecked():
                return new_pos
            
            items = [i for i in self.scene().items() if isinstance(i, FieldItem) and i != self]
            if not items:
                return new_pos

            snap_threshold = 5
            my_rect = self.rect().translated(new_pos)
            my_center_x = my_rect.center().x()
            my_center_y = my_rect.center().y()

            target_centers_x, target_edges_x = [], []
            target_centers_y, target_edges_y = [], []

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

            # EJE X - Prioridad Absoluta: Alinear por el Centro
            min_dx = snap_threshold
            for tx in target_centers_x:
                if abs(tx - my_center_x) < min_dx:
                    min_dx = abs(tx - my_center_x)
                    best_new_x = tx - self.rect().center().x()
                    guide_x = tx
                    snapped_x = True

            # Si no ha pillado centro, busca bordes
            if not snapped_x:
                min_dx = snap_threshold
                my_edges_x = {'left': my_rect.left(), 'right': my_rect.right()}
                for tx in target_edges_x:
                    for my_key, my_x in my_edges_x.items():
                        if abs(tx - my_x) < min_dx:
                            min_dx = abs(tx - my_x)
                            if my_key == 'left': best_new_x = tx - self.rect().left()
                            elif my_key == 'right': best_new_x = tx - self.rect().right()
                            guide_x = tx
                            snapped_x = True

            # EJE Y - Prioridad Absoluta: Alinear por el Centro
            min_dy = snap_threshold
            for ty in target_centers_y:
                if abs(ty - my_center_y) < min_dy:
                    min_dy = abs(ty - my_center_y)
                    best_new_y = ty - self.rect().center().y()
                    guide_y = ty
                    snapped_y = True

            # Si no ha pillado centro, busca bordes
            if not snapped_y:
                min_dy = snap_threshold
                my_edges_y = {'top': my_rect.top(), 'bottom': my_rect.bottom()}
                for ty in target_edges_y:
                    for my_key, my_y in my_edges_y.items():
                        if abs(ty - my_y) < min_dy:
                            min_dy = abs(ty - my_y)
                            if my_key == 'top': best_new_y = ty - self.rect().top()
                            elif my_key == 'bottom': best_new_y = ty - self.rect().bottom()
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
            
            if hasattr(self.scene(), 'clear_guides'):
                self.scene().clear_guides()
                
            # Solo snappear tamaño si el imán está activado
            if mw and mw.action_toggle_snap.isChecked():
                items = [i for i in self.scene().items() if isinstance(i, FieldItem) and i != self]
                if items:
                    target_centers_x, target_edges_x = [], []
                    target_centers_y, target_edges_y = [], []
                    
                    for item in items:
                        other_rect = item.sceneBoundingRect()
                        if abs(scene_pos.y() - other_rect.center().y()) < 2000:
                            target_centers_x.append(other_rect.center().x())
                            target_edges_x.extend([other_rect.left(), other_rect.right()])
                            target_centers_y.append(other_rect.center().y())
                            target_edges_y.extend([other_rect.top(), other_rect.bottom()])
                    
                    snap_threshold = 5
                    check_x = self.active_handle in ['tl', 'tr', 'lc', 'rc', 'bl', 'br']
                    check_y = self.active_handle in ['tl', 'tc', 'tr', 'bl', 'bc', 'br']

                    if check_x:
                        min_dx = snap_threshold
                        best_x = scene_pos.x()
                        # Prioridad Centro
                        for tx in target_centers_x:
                            if abs(scene_pos.x() - tx) < min_dx:
                                min_dx = abs(scene_pos.x() - tx)
                                best_x = tx
                        # Si no, Bordes
                        if min_dx == snap_threshold:
                            for tx in target_edges_x:
                                if abs(scene_pos.x() - tx) < min_dx:
                                    min_dx = abs(scene_pos.x() - tx)
                                    best_x = tx
                                    
                        if min_dx < snap_threshold:
                            scene_pos.setX(best_x)
                            self.scene().add_guide_line(best_x, True)

                    if check_y:
                        min_dy = snap_threshold
                        best_y = scene_pos.y()
                        # Prioridad Centro
                        for ty in target_centers_y:
                            if abs(scene_pos.y() - ty) < min_dy:
                                min_dy = abs(scene_pos.y() - ty)
                                best_y = ty
                        # Si no, Bordes
                        if min_dy == snap_threshold:
                            for ty in target_edges_y:
                                if abs(scene_pos.y() - ty) < min_dy:
                                    min_dy = abs(scene_pos.y() - ty)
                                    best_y = ty
                                    
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
        if hasattr(self.scene(), 'clear_guides'):
            self.scene().clear_guides()

        if self.resizing or self.start_pos != self.pos():
            if hasattr(self.scene(), 'main_window'):
                mw = self.scene().main_window
                cmd = ModifyFieldCommand(self, self.start_rect, self.start_pos, self.rect(), self.pos())
                mw.undo_stack.push(cmd)

        self.resizing = False
        self.active_handle = None
        super().mouseReleaseEvent(event)


# ================= VISTA Y MANEJO DE HERRAMIENTAS =================

class CustomScene(QGraphicsScene):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.guide_lines = []

    def add_guide_line(self, pos, is_vertical):
        pen = QPen(QColor("#E91E63"), 1.5, Qt.DashLine) 
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
        
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.rubber_band.setStyleSheet("QRubberBand { background-color: rgba(103, 80, 164, 50); border: 2px solid #6750A4; }")
        
        self.origin = QPoint()
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

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
            zoom_in_factor = 1.15
            zoom_out_factor = 1.0 / zoom_in_factor
            
            if event.angleDelta().y() > 0:
                self.scale(zoom_in_factor, zoom_in_factor)
            else:
                self.scale(zoom_out_factor, zoom_out_factor)
            
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

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile() and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.accept()
                return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.main_window.load_pdf(file_path)
                event.accept()
                return
        super().dropEvent(event)


# ================= VENTANA PRINCIPAL =================

class PDFFormEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDFormer - Editor de Formularios PDF")
        self.setGeometry(100, 100, 1280, 800)
        self.setAcceptDrops(True)

        self.apply_material_theme()

        self.current_file_path = None
        self.doc = None
        self.current_page = 0
        self.zoom = 1.5  
        self.current_tool = None
        
        self.undo_stack = QUndoStack(self)
        self.all_fields = set() 
        self.page_rects = {} 
        self.copied_field_data = None

        self.viewer = PDFViewer(self)
        self.setCentralWidget(self.viewer)
        self.status_label = QLabel("✨ Bienvenido a PDFormer. Abre o arrastra un documento PDF para empezar.")
        self.statusBar().addWidget(self.status_label)

        self.setup_actions()
        self.create_menus()
        self.create_toolbars()
        self.create_statusbar_nav()

    def apply_material_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #FDFBFF; }
            
            /* Ajuste de espaciado general de barras */
            QToolBar { background-color: #FEF7FF; border: none; spacing: 4px; padding: 4px; }
            QToolBar:top { border-bottom: 1px solid #E7E0EC; }
            
            QToolBar:left { 
                border-right: 1px solid #E7E0EC; 
                min-width: 110px; 
                padding: 10px 6px; 
                background-color: #FDFBFF;
            }
            
            /* Botones Superiores limpios sin bordes fijos */
            QToolBar:top QToolButton { 
                font-family: "Segoe UI", Roboto, sans-serif; 
                font-size: 13px; 
                font-weight: 500; 
                color: #49454F; 
                background-color: transparent; 
                padding: 6px 12px; 
                border-radius: 6px; 
                border: 1px solid transparent;
            }
            
            /* Botones del panel lateral más compactos */
            QToolBar:left QToolButton { 
                font-family: "Segoe UI", Roboto, sans-serif; 
                font-size: 12px; 
                font-weight: 600; 
                color: #49454F; 
                background-color: transparent; 
                border: 1px solid transparent;
                padding: 8px 4px; 
                border-radius: 8px;
                margin-bottom: 4px; 
                width: 100%; 
                text-align: center; 
            }
            
            /* Animaciones suaves */
            QToolButton:hover { 
                background-color: #EADDFF; 
                color: #21005D; 
            }
            
            /* Efecto click sin descuadrar el layout */
            QToolBar:top QToolButton:pressed, QToolBar:left QToolButton:pressed { 
                background-color: #D0BCFF; 
            }
            
            /* Estilo para botones pulsados (como el botón Imán activado) */
            QToolButton:checked {
                background-color: #D0BCFF;
                color: #21005D;
            }
            
            QMenuBar { background-color: #FEF7FF; border-bottom: 1px solid #E7E0EC; font-family: "Segoe UI", Roboto, sans-serif; }
            QMenuBar::item { padding: 6px 10px; background: transparent; border-radius: 4px; margin: 2px; }
            QMenuBar::item:selected { background: #EADDFF; color: #21005D; }
            QLabel { font-family: "Segoe UI", Roboto, sans-serif; font-size: 13px; color: #49454F; padding: 4px 8px; }
            QGraphicsView { background-color: #F0EBF4; border: none; }
            QStatusBar { background-color: #FEF7FF; border-top: 1px solid #E7E0EC; }
            QScrollBar:vertical { border: none; background: #FDFBFF; width: 12px; margin: 0px; }
            QScrollBar::handle:vertical { background: #CAC4D0; min-height: 20px; border-radius: 6px; margin: 2px; }
            QScrollBar::handle:vertical:hover { background: #AFA9B4; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar:horizontal { border: none; background: #FDFBFF; height: 12px; margin: 0px; }
            QScrollBar::handle:horizontal { background: #CAC4D0; min-width: 20px; border-radius: 6px; margin: 2px; }
            QScrollBar::handle:horizontal:hover { background: #AFA9B4; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
        """)

    def setup_actions(self):
        self.action_new = QAction("📄 Nuevo PDF", self, shortcut="Ctrl+N", triggered=self.new_pdf)
        self.action_open = QAction("📂 Abrir PDF", self, shortcut="Ctrl+O", triggered=self.open_pdf)
        
        self.action_save = QAction("💾 Guardar", self, shortcut="Ctrl+S", triggered=self.save_pdf)
        self.action_save_as = QAction("💾 Guardar como...", self, shortcut="Ctrl+Shift+S", triggered=self.save_pdf_as)
        
        self.action_exit = QAction("❌ Salir", self, shortcut="Ctrl+Q", triggered=self.close)

        self.action_prev = QAction("⬆️ Página Anterior", self, triggered=self.prev_page)
        self.action_next = QAction("Página Siguiente ⬇️", self, triggered=self.next_page)
        
        self.action_add_page = QAction("➕ Añadir Página", self, triggered=self.add_blank_page)
        self.action_delete_page = QAction("🗑️ Borrar Página", self, triggered=self.delete_current_page)
        
        # FIX: Evitamos el default de QUndoStack que cambiaba el texto dinámicamente ("Deshacer Añadir Elemento")
        self.action_undo = QAction("↩️ Deshacer", self, shortcut=QKeySequence.Undo, triggered=self.undo_stack.undo)
        self.action_redo = QAction("↪️ Rehacer", self, shortcut=QKeySequence.Redo, triggered=self.undo_stack.redo)
        
        # Conectamos las acciones para que se apaguen solas si no hay nada que deshacer/rehacer
        self.action_undo.setEnabled(False)
        self.action_redo.setEnabled(False)
        self.undo_stack.canUndoChanged.connect(self.action_undo.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.action_redo.setEnabled)
        
        self.action_copy = QAction("📄 Copiar", self, shortcut="Ctrl+C", triggered=self.copy_field)
        self.action_paste = QAction("📋 Pegar", self, shortcut="Ctrl+V", triggered=self.paste_field)
        self.action_delete = QAction("🗑️ Eliminar", self, shortcut="Del", triggered=self.delete_selected_field)

        # Imán Magnético para la barra lateral
        self.action_toggle_snap = QAction("🧲 Imán (Guías)", self, checkable=True)
        self.action_toggle_snap.setChecked(True)

        # Nombres simplificados sin saltos de línea y minimalistas
        self.action_cursor = QAction("👆 Cursor", self, triggered=lambda: self.set_tool(None))
        self.action_static_text = QAction("🔤 Texto Libre", self, triggered=lambda: self.set_tool('static_text'))
        self.action_whiteout = QAction("⬜ Típex", self, triggered=lambda: self.set_tool('whiteout'))
        self.action_text = QAction("📝 Texto", self, triggered=lambda: self.set_tool('text'))
        self.action_textarea = QAction("📑 Multilínea", self, triggered=lambda: self.set_tool('textarea'))
        self.action_check = QAction("☑️ Checkbox", self, triggered=lambda: self.set_tool('checkbox'))
        self.action_combo = QAction("🔽 Desplegable", self, triggered=lambda: self.set_tool('dropdown'))
        self.action_signature = QAction("🖋️ Firma", self, triggered=lambda: self.set_tool('signature'))

        self.addAction(self.action_delete)
        self.addAction(self.action_copy)
        self.addAction(self.action_paste)

    def create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&Archivo")
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_open)
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        edit_menu = menubar.addMenu("&Edición")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_copy)
        edit_menu.addAction(self.action_paste)
        edit_menu.addAction(self.action_delete)

        pages_menu = menubar.addMenu("&Páginas")
        pages_menu.addAction(self.action_add_page)
        pages_menu.addAction(self.action_delete_page)

        tools_menu = menubar.addMenu("&Herramientas")
        tools_menu.addAction(self.action_cursor)
        tools_menu.addAction(self.action_toggle_snap)
        tools_menu.addSeparator()
        tools_menu.addAction(self.action_static_text)
        tools_menu.addAction(self.action_whiteout)
        tools_menu.addSeparator()
        tools_menu.addAction(self.action_text)
        tools_menu.addAction(self.action_textarea)
        tools_menu.addAction(self.action_check)
        tools_menu.addAction(self.action_combo)
        tools_menu.addSeparator()
        tools_menu.addAction(self.action_signature)

    def create_toolbars(self):
        # Eliminamos la barra superior de "Archivo"
        
        edit_toolbar = QToolBar("Edición")
        self.addToolBar(Qt.TopToolBarArea, edit_toolbar)
        edit_toolbar.addAction(self.action_undo)
        edit_toolbar.addAction(self.action_redo)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.action_copy)
        edit_toolbar.addAction(self.action_paste)
        edit_toolbar.addAction(self.action_delete)

        pages_toolbar = QToolBar("Páginas")
        self.addToolBar(Qt.TopToolBarArea, pages_toolbar)
        pages_toolbar.addAction(self.action_add_page)
        pages_toolbar.addAction(self.action_delete_page)

        tools_toolbar = QToolBar("Herramientas")
        self.addToolBar(Qt.LeftToolBarArea, tools_toolbar)
        tools_toolbar.addAction(self.action_cursor)
        tools_toolbar.addAction(self.action_toggle_snap)
        tools_toolbar.addSeparator()
        tools_toolbar.addAction(self.action_static_text)
        tools_toolbar.addAction(self.action_whiteout)
        tools_toolbar.addSeparator()
        tools_toolbar.addAction(self.action_text)
        tools_toolbar.addAction(self.action_textarea)
        tools_toolbar.addAction(self.action_check)
        tools_toolbar.addAction(self.action_combo)
        tools_toolbar.addSeparator()
        tools_toolbar.addAction(self.action_signature)

        for tb in [edit_toolbar, pages_toolbar, tools_toolbar]:
            tb.setMovable(False)
            tb.setToolButtonStyle(Qt.ToolButtonTextOnly)

    def create_statusbar_nav(self):
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 10, 0)
        nav_layout.setSpacing(5)
        
        btn_prev = QToolButton()
        btn_prev.setDefaultAction(self.action_prev)
        btn_prev.setToolButtonStyle(Qt.ToolButtonTextOnly)
        
        self.page_label = QLabel(" 0 / 0 ")
        self.page_label.setStyleSheet("font-weight: bold; color: #6750A4; font-size: 13px; padding: 0 10px;")
        self.page_label.setAlignment(Qt.AlignCenter)
        
        btn_next = QToolButton()
        btn_next.setDefaultAction(self.action_next)
        btn_next.setToolButtonStyle(Qt.ToolButtonTextOnly)
        
        nav_layout.addWidget(btn_prev)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(btn_next)
        
        self.statusBar().addPermanentWidget(nav_widget)

    def set_tool(self, tool_name):
        self.current_tool = tool_name
        if tool_name:
            self.status_label.setText(f"✏️ Modo Dibujo activo. Haz clic y arrastra en el PDF.")
            self.viewer.setCursor(Qt.CrossCursor)
            self.viewer.scene.clearSelection()
        else:
            self.status_label.setText("👆 Modo Cursor. Selecciona, arrastra o redimensiona elementos libremente.")
            self.viewer.setCursor(Qt.ArrowCursor)

    def new_pdf(self):
        if self.doc and not self.undo_stack.isClean():
            reply = QMessageBox.question(self, "Documento sin guardar", "Hay cambios sin guardar. ¿Desea descartarlos y crear un nuevo PDF?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No: return
        
        self.current_file_path = None
        self.doc = fitz.open()
        self.doc.new_page(width=595, height=842) # A4 estándar
        self.current_page = 0
        self.all_fields.clear()
        self.undo_stack.clear()
        self.render_document()
        self.update_page_label()
        self.status_label.setText("📄 Nuevo documento creado.")
        self.setWindowTitle("PDFormer - Sin Título")

    def open_pdf(self):
        if self.doc and not self.undo_stack.isClean():
            reply = QMessageBox.question(self, "Documento sin guardar", "Hay cambios sin guardar. ¿Desea descartarlos para abrir un nuevo documento?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No: return

        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "PDF (*.pdf)")
        if file_path:
            self.load_pdf(file_path)

    def load_pdf(self, file_path):
        try:
            with open(file_path, "rb") as f:
                pdf_data = f.read()
            self.doc = fitz.open("pdf", pdf_data)
            self.current_file_path = file_path
            
            self.current_page = 0
            self.all_fields.clear()
            self.undo_stack.clear()
            self.render_document()
            self.update_page_label()
            self.status_label.setText(f"📄 Documento cargado: {file_path}")
            self.setWindowTitle(f"PDFormer - {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el PDF:\n{str(e)}")

    def add_blank_page(self):
        if not self.doc:
            self.new_pdf()
            return
            
        w = self.doc[self.current_page].rect.width
        h = self.doc[self.current_page].rect.height
        
        new_idx = self.current_page + 1
        self.doc.new_page(pno=new_idx, width=w, height=h)
        
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = self.doc[self.current_page].get_pixmap(matrix=mat)
        gap = 30
        shift_amount = pix.height + gap
        
        boundary_y = self.page_rects[self.current_page].bottom()
        
        for item in self.all_fields:
            try:
                if item.sceneBoundingRect().center().y() > boundary_y:
                    item.setPos(item.x(), item.y() + shift_amount)
            except RuntimeError: pass
                
        self.current_page = new_idx
        self.render_document()
        self.update_page_label()
        
        if new_idx in self.page_rects:
            self.viewer.verticalScrollBar().setValue(int(self.page_rects[new_idx].top()))
            
        self.status_label.setText(f"➕ Página {new_idx + 1} añadida.")

    def delete_current_page(self):
        if not self.doc or len(self.doc) == 0: return
        
        if len(self.doc) == 1:
            QMessageBox.warning(self, "Aviso", "No puedes eliminar la única página del documento. Crea una nueva primero o cierra el archivo.")
            return

        reply = QMessageBox.question(self, "Confirmar Eliminación", f"¿Seguro que quieres eliminar la página {self.current_page + 1}?\n⚠️ Se perderán todos los elementos que contenga.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No: return
        
        p_rect = self.page_rects[self.current_page]
        gap = 30
        shift_amount = p_rect.height() + gap
        
        items_to_remove = []
        for item in self.all_fields:
            try:
                cy = item.sceneBoundingRect().center().y()
                if p_rect.top() <= cy <= p_rect.bottom():
                    items_to_remove.append(item)
                elif cy > p_rect.bottom():
                    item.setPos(item.x(), item.y() - shift_amount)
            except RuntimeError: pass
                
        for item in items_to_remove:
            try:
                if item.scene() == self.viewer.scene:
                    self.viewer.scene.removeItem(item)
                self.all_fields.discard(item)
            except RuntimeError: pass
            
        self.doc.delete_page(self.current_page)
        
        if self.current_page >= len(self.doc):
            self.current_page = len(self.doc) - 1
            
        self.render_document()
        self.update_page_label()
        
        if self.current_page in self.page_rects:
            self.viewer.verticalScrollBar().setValue(int(self.page_rects[self.current_page].top()))
            
        self.status_label.setText("🗑️ Página eliminada.")

    def create_field(self, scene_rect):
        timestamp = int(time.time() * 1000)
        name = f"Campo_{timestamp}"
        options = None
        text_content = ""
        
        has_border = True
        if self.current_tool in ['static_text', 'whiteout']:
            has_border = False

        if self.current_tool == 'dropdown':
            dialog = QInputDialog(self)
            dialog.setWindowTitle("Desplegable")
            dialog.setLabelText("Opciones separadas por coma:")
            dialog.setStyleSheet("QInputDialog { background-color: #FEF7FF; } QLineEdit { padding: 6px; border: 1px solid #CAC4D0; border-radius: 4px; }")
            if dialog.exec_():
                opts = dialog.textValue()
                if opts.strip():
                    options = [o.strip() for o in opts.split(',') if o.strip()]
            if not options:
                return
        
        elif self.current_tool == 'static_text':
            text, ok = QInputDialog.getMultiLineText(self, "Texto Libre", "Escribe el texto a insertar:")
            if not ok or not text.strip():
                return
            text_content = text.strip()

        item = FieldItem(scene_rect, self.current_tool, name, options, has_border=has_border, text_content=text_content)
        cmd = AddFieldCommand(self.viewer.scene, item, self.all_fields)
        self.undo_stack.push(cmd)
        
        self.set_tool(None)

    def delete_selected_field(self):
        for item in self.viewer.scene.selectedItems():
            if isinstance(item, FieldItem):
                cmd = RemoveFieldCommand(self.viewer.scene, item, self.all_fields)
                self.undo_stack.push(cmd)

    def copy_field(self):
        items = self.viewer.scene.selectedItems()
        if items and isinstance(items[0], FieldItem):
            item = items[0]
            try:
                self.copied_field_data = {
                    'type': item.field_type,
                    'rect': item.rect(),
                    'options': item.options,
                    'has_border': item.has_border,
                    'text_content': item.text_content
                }
                self.status_label.setText("✅ Elemento copiado al portapapeles.")
            except RuntimeError: pass

    def paste_field(self):
        if not self.copied_field_data: return
        
        data = self.copied_field_data
        new_rect = data['rect'].translated(20, 20)
        timestamp = int(time.time() * 1000)
        
        item = FieldItem(new_rect, data['type'], f"CampoCopiado_{timestamp}", data['options'], data.get('has_border', True), data.get('text_content', ""))
        cmd = AddFieldCommand(self.viewer.scene, item, self.all_fields)
        self.undo_stack.push(cmd)
        
        self.viewer.scene.clearSelection()
        item.setSelected(True)

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            y_pos = self.page_rects[self.current_page].top()
            self.viewer.verticalScrollBar().setValue(int(y_pos))
            self.update_page_label()

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            y_pos = self.page_rects[self.current_page].top()
            self.viewer.verticalScrollBar().setValue(int(y_pos))
            self.update_page_label()

    def update_page_label(self):
        if not self.doc or not self.page_rects: 
            self.page_label.setText(" 0 / 0 ")
            return
        view_center_y = self.viewer.mapToScene(self.viewer.viewport().rect().center()).y()
        
        current_p = 0
        for p_num, p_rect in self.page_rects.items():
            if p_rect.top() <= view_center_y <= p_rect.bottom() + 30:
                current_p = p_num
                break
                
        self.current_page = current_p
        self.action_prev.setEnabled(self.current_page > 0)
        self.action_next.setEnabled(self.current_page < len(self.doc) - 1)
        self.page_label.setText(f" {self.current_page + 1} / {len(self.doc)} ")

    def render_document(self):
        if not self.doc: return
        
        for item in list(self.viewer.scene.items()):
            try:
                if isinstance(item, FieldItem):
                    item.hide()
                elif item.parentItem() is None:
                    self.viewer.scene.removeItem(item)
            except RuntimeError: pass
                
        self.viewer.scene.guide_lines.clear()
        self.page_rects.clear()
        
        current_y = 0
        gap = 30 
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            mat = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=mat, annots=True)
            
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            
            bg_item = self.viewer.scene.addPixmap(pixmap)
            bg_item.setPos(0, current_y)
            bg_item.setZValue(-1) 
            
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(20)
            shadow.setXOffset(0)
            shadow.setYOffset(4)
            shadow.setColor(QColor(0, 0, 0, 50))
            bg_item.setGraphicsEffect(shadow)
            
            self.page_rects[page_num] = QRectF(0, current_y, pix.width, pix.height)
            current_y += pix.height + gap

        if self.page_rects:
            self.viewer.setSceneRect(self.viewer.scene.itemsBoundingRect())

        for item in self.all_fields:
            try:
                if item.scene() is None:
                    self.viewer.scene.addItem(item)
                item.show()
            except RuntimeError: pass

    def save_pdf(self):
        if not self.doc: return False
        if self.current_file_path:
            return self._perform_save(self.current_file_path)
        else:
            return self.save_pdf_as()
            
    def save_pdf_as(self):
        if not self.doc: return False
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar como...", "", "PDF (*.pdf)")
        if not file_path: return False
        
        if self._perform_save(file_path):
            self.current_file_path = file_path
            self.setWindowTitle(f"PDFormer - {file_path}")
            self.status_label.setText(f"📄 Documento guardado en: {file_path}")
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
            except Exception:
                pass

            for item in self.all_fields:
                try:
                    if item.scene() is None: continue 
                    item_center_y = item.sceneBoundingRect().center().y()
                    final_rect = item.sceneBoundingRect()
                except RuntimeError:
                    continue 
                
                target_page = 0
                
                for p_num, p_rect in self.page_rects.items():
                    if p_rect.top() <= item_center_y <= p_rect.bottom() + 30:
                        target_page = p_num
                        break
                
                page = export_doc[target_page]
                p_rect = self.page_rects[target_page]
                
                x0 = (final_rect.left() - p_rect.left()) / self.zoom
                y0 = (final_rect.top() - p_rect.top()) / self.zoom
                x1 = (final_rect.right() - p_rect.left()) / self.zoom
                y1 = (final_rect.bottom() - p_rect.top()) / self.zoom

                fitz_rect = fitz.Rect(x0, y0, x1, y1)

                if item.field_type == 'whiteout':
                    page.draw_rect(fitz_rect, color=(1,1,1), fill=(1,1,1))
                    if item.has_border:
                        page.draw_rect(fitz_rect, color=(0,0,0), fill=None, width=1)
                
                elif item.field_type == 'static_text':
                    if item.has_border:
                        page.draw_rect(fitz_rect, color=(0,0,0), fill=None, width=1)
                    page.insert_textbox(fitz_rect, item.text_content, fontsize=11, fontname="helv", color=(0,0,0), align=0)
                
                else:
                    widget = fitz.Widget()
                    widget.rect = fitz_rect
                    
                    if item.field_type != 'signature':
                        widget.fill_color = (0.85, 0.9, 1.0)
                    
                    if item.has_border:
                        widget.border_color = (0, 0, 0)
                        widget.border_width = 1
                    else:
                        widget.border_width = 0

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
                        xref = getattr(widget, 'xref', None)
                        if not xref and new_widget:
                            xref = getattr(new_widget, 'xref', None)
                        if not xref:
                            annot = page.first_widget
                            while annot:
                                if getattr(annot, 'field_name', '') == item.field_name:
                                    xref = annot.xref
                                    break
                                annot = annot.next
                        if xref:
                            export_doc.xref_set_key(xref, "Lock", "<< /Action /All >>")

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
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Documento sin guardar")
            msg_box.setText("Hay documentos sin guardar.\n¿Está seguro de que desea cerrar el programa?")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStyleSheet("QMessageBox { background-color: #FEF7FF; } QPushButton { padding: 6px 16px; border-radius: 6px; background: #EADDFF; border: 1px solid #CAC4D0; }")

            btn_save = msg_box.addButton("Guardar", QMessageBox.AcceptRole)
            btn_yes = msg_box.addButton("Sí", QMessageBox.DestructiveRole)
            btn_no = msg_box.addButton("No", QMessageBox.RejectRole)

            msg_box.setDefaultButton(btn_save)
            msg_box.exec_()

            if msg_box.clickedButton() == btn_save:
                if self.save_pdf():
                    event.accept()
                else:
                    event.ignore()
            elif msg_box.clickedButton() == btn_yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion') 
    editor = PDFFormEditor()
    editor.show()
    sys.exit(app.exec_())