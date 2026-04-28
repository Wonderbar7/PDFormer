import time
import qtawesome as qta
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem, QMenu, QInputDialog, QMessageBox
from PyQt5.QtGui import QColor, QBrush, QPen, QFont, QPainter
from PyQt5.QtCore import Qt, QRectF, QPointF
from logic.commands import ModifyFieldCommand, ToggleBorderCommand, ChangeTextCommand, AddFieldCommand

class ResizeHandle(QGraphicsRectItem):
    """ Puntos para redimensionar el campo (Material Style) """
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
    """ Representa un campo o elemento que flota sobre el PDF """
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
            mw = self.get_main_window()
            if mw:
                cmd = ToggleBorderCommand(self, not self.has_border)
                mw.undo_stack.push(cmd)
        elif edit_text_action and action == edit_text_action:
            mw = self.get_main_window()
            if mw:
                new_text, ok = QInputDialog.getMultiLineText(mw, "Editar Texto Libre", "Escribe el nuevo texto:", self.text_content)
                if ok and new_text != self.text_content:
                    cmd = ChangeTextCommand(self, self.text_content, new_text)
                    mw.undo_stack.push(cmd)
        elif action == resize_action:
            mw = self.get_main_window()
            if mw:
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

    def get_main_window(self):
        if self.scene() and hasattr(self.scene(), 'main_window'):
            return self.scene().main_window
        return None

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
            mw = self.get_main_window()
            
            if hasattr(self.scene(), 'clear_guides'):
                self.scene().clear_guides()
                
            if mw and not mw.snap_enabled:
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

            # EJE X
            min_dx = snap_threshold
            for tx in target_centers_x:
                if abs(tx - my_center_x) < min_dx:
                    min_dx = abs(tx - my_center_x)
                    best_new_x = tx - self.rect().center().x()
                    guide_x = tx
                    snapped_x = True

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

            # EJE Y
            min_dy = snap_threshold
            for ty in target_centers_y:
                if abs(ty - my_center_y) < min_dy:
                    min_dy = abs(ty - my_center_y)
                    best_new_y = ty - self.rect().center().y()
                    guide_y = ty
                    snapped_y = True

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
            mw = self.get_main_window()
            if mw:
                clone = FieldItem(self.rect(), self.field_type, f"Copia_{int(time.time() * 1000)}", self.options, self.has_border, self.text_content)
                clone.setPos(self.pos())
                cmd = AddFieldCommand(self.scene(), clone, mw.all_fields)
                mw.undo_stack.push(cmd)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            mouse_pos = event.pos()
            scene_pos = self.mapToScene(mouse_pos)
            mw = self.get_main_window()
            
            if hasattr(self.scene(), 'clear_guides'):
                self.scene().clear_guides()
                
            if mw and mw.snap_enabled:
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
                        for tx in target_centers_x:
                            if abs(scene_pos.x() - tx) < min_dx:
                                min_dx = abs(scene_pos.x() - tx)
                                best_x = tx
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
                        for ty in target_centers_y:
                            if abs(scene_pos.y() - ty) < min_dy:
                                min_dy = abs(scene_pos.y() - ty)
                                best_y = ty
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
            mw = self.get_main_window()
            if mw:
                cmd = ModifyFieldCommand(self, self.start_rect, self.start_pos, self.rect(), self.pos())
                mw.undo_stack.push(cmd)

        self.resizing = False
        self.active_handle = None
        super().mouseReleaseEvent(event)
