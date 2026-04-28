from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QCheckBox, QPushButton, QFormLayout, QGroupBox, 
                             QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QRectF
from ui.items import FieldItem
from logic.commands import ModifyFieldCommand, ChangeTextCommand, ToggleBorderCommand

class PropertiesPanel(QScrollArea):
    """ Panel lateral para editar las propiedades del elemento seleccionado """
    property_changed = pyqtSignal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWidgetResizable(True)
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)
        
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(15)
        
        self.setWidget(self.container)
        self.setStyleSheet("""
            QWidget { background-color: #f8f9fc; }
            QGroupBox { font-weight: bold; border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 10px; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; color: #64748b; font-size: 11px; text-transform: uppercase; }
            QLabel { color: #475569; font-size: 12px; }
            QLineEdit { padding: 6px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; }
            QPushButton { background-color: #0b50da; color: white; border-radius: 6px; padding: 8px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #0940b0; }
        """)

        self.current_item = None
        self.setup_ui()
        self.hide()

    def setup_ui(self):
        # Grupo Identificación
        self.id_group = QGroupBox("Identificación")
        id_layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self.update_item_name)
        id_layout.addRow("ID / Nombre:", self.name_edit)
        self.type_label = QLabel("-")
        id_layout.addRow("Tipo:", self.type_label)
        self.id_group.setLayout(id_layout)
        self.layout.addWidget(self.id_group)

        # Grupo Geometría
        self.geo_group = QGroupBox("Posición y Tamaño")
        geo_layout = QFormLayout()
        self.x_edit = QLineEdit(); self.y_edit = QLineEdit()
        self.w_edit = QLineEdit(); self.h_edit = QLineEdit()
        
        for edit in [self.x_edit, self.y_edit, self.w_edit, self.h_edit]:
            edit.editingFinished.connect(self.apply_geometry)
            
        geo_layout.addRow("X:", self.x_edit)
        geo_layout.addRow("Y:", self.y_edit)
        geo_layout.addRow("Ancho:", self.w_edit)
        geo_layout.addRow("Alto:", self.h_edit)
        self.geo_group.setLayout(geo_layout)
        self.layout.addWidget(self.geo_group)

        # Grupo Apariencia
        self.app_group = QGroupBox("Apariencia")
        app_layout = QVBoxLayout()
        self.border_check = QCheckBox("Mostrar Borde")
        self.border_check.toggled.connect(self.update_border)
        app_layout.addWidget(self.border_check)
        self.app_group.setLayout(app_layout)
        self.layout.addWidget(self.app_group)

        # Grupo Contenido (Solo para texto)
        self.content_group = QGroupBox("Contenido")
        content_layout = QVBoxLayout()
        self.text_edit = QLineEdit()
        self.text_edit.textChanged.connect(self.update_text_content)
        content_layout.addWidget(QLabel("Texto:"))
        content_layout.addWidget(self.text_edit)
        self.content_group.setLayout(content_layout)
        self.layout.addWidget(self.content_group)
        
        self.layout.addStretch()

    def set_item(self, item):
        self.current_item = item
        if not item:
            self.hide()
            return

        self.show()
        self.name_edit.setText(item.field_name)
        self.type_label.setText(item.field_type.capitalize())
        
        rect = item.rect()
        pos = item.pos()
        self.x_edit.setText(str(int(pos.x())))
        self.y_edit.setText(str(int(pos.y())))
        self.w_edit.setText(str(int(rect.width())))
        self.h_edit.setText(str(int(rect.height())))
        
        self.border_check.setChecked(item.has_border)
        
        if item.field_type == 'static_text':
            self.content_group.show()
            self.text_edit.setText(item.text_content)
        else:
            self.content_group.hide()

    def update_item_name(self, text):
        if self.current_item:
            self.current_item.field_name = text

    def update_text_content(self, text):
        if self.current_item and self.current_item.text_content != text:
            # Nota: Aquí no usamos UndoStack directamente para evitar ruido al escribir, 
            # pero podríamos usar un timer o editingFinished
            self.current_item.text_content = text
            self.current_item.update()

    def update_border(self, checked):
        if self.current_item and self.current_item.has_border != checked:
            cmd = ToggleBorderCommand(self.current_item, checked)
            self.main_window.undo_stack.push(cmd)

    def apply_geometry(self):
        if not self.current_item: return
        try:
            new_pos = QPointF(float(self.x_edit.text()), float(self.y_edit.text()))
            new_rect = QRectF(0, 0, float(self.w_edit.text()), float(self.h_edit.text()))
            
            if new_pos != self.current_item.pos() or new_rect != self.current_item.rect():
                cmd = ModifyFieldCommand(self.current_item, self.current_item.rect(), self.current_item.pos(), new_rect, new_pos)
                self.main_window.undo_stack.push(cmd)
        except ValueError:
            pass
