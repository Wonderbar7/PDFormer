from PyQt5.QtWidgets import QUndoCommand
from PyQt5.QtCore import Qt, QRectF

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
