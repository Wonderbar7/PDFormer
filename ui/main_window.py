import sys
import time
import os
import fitz  # PyMuPDF
import qtawesome as qta
from PyQt5.QtWidgets import (QMainWindow, QFileDialog, QMessageBox, QInputDialog, 
                             QLabel, QAction, QMenu, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QUndoStack, QGraphicsDropShadowEffect,
                             QFrame, QGridLayout, QApplication)
from PyQt5.QtGui import QImage, QPixmap, QColor, QFont, QTransform, QIcon
from PyQt5.QtCore import Qt, QRectF, QSize

from ui.viewer import PDFViewer
from ui.items import FieldItem
from ui.properties_panel import PropertiesPanel
from logic.commands import AddFieldCommand, RemoveFieldCommand, ModifyFieldCommand

class PDFFormEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Configuración de fuente base
        app_font = QFont("Segoe UI", 10)
        app_font.setStyleHint(QFont.SansSerif)
        QApplication.instance().setFont(app_font)

        self.setWindowTitle("PDFormer - Editor de Formularios PDF")
        self.setGeometry(100, 100, 1280, 800)
        self.setAcceptDrops(True)
        self.setStyleSheet("QMainWindow { background-color: #f8f9fc; font-family: 'Segoe UI', 'Helvetica Neue', sans-serif; }")

        # Icono de la ventana
        self.logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.svg")
        if os.path.exists(self.logo_path):
            self.setWindowIcon(QIcon(self.logo_path))

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
        
        self.close_document() # Inicia en estado vacío

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. HEADER (Material 3 Style)
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(56)
        header.setStyleSheet("""
            #header { 
                background-color: white; 
                border-bottom: 1px solid #e2e8f0; 
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 1)
        header_layout.setSpacing(0)
        
        # Logo y Título
        logo_layout = QHBoxLayout()
        self.logo_icon_label = QLabel()
        if os.path.exists(self.logo_path):
            self.logo_icon_label.setPixmap(QIcon(self.logo_path).pixmap(24, 24))
            self.logo_icon_label.setStyleSheet("padding: 2px;")
        else:
            self.logo_icon_label.setPixmap(qta.icon('fa5s.file-pdf', color='white').pixmap(20, 20))
            self.logo_icon_label.setStyleSheet("background-color: #0b50da; border-radius: 8px; padding: 6px;")
        
        title = QLabel("PDFormer")
        title.setStyleSheet("font-weight: bold; font-size: 18px; color: #0f172a; border: none; background: transparent;")
        logo_layout.addWidget(self.logo_icon_label)
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

        # Botones de Acción Rápidos
        right_header = QHBoxLayout()
        ur_container = QWidget()
        ur_container.setStyleSheet("background-color: #f1f5f9; border-radius: 8px;")
        ur_layout = QHBoxLayout(ur_container)
        ur_layout.setContentsMargins(4, 4, 4, 4)
        ur_layout.setSpacing(2)
        
        self.btn_undo = self.create_icon_btn("fa5s.undo-alt", "Deshacer")
        self.btn_redo = self.create_icon_btn("fa5s.redo-alt", "Rehacer")
        ur_layout.addWidget(self.btn_undo)
        ur_layout.addWidget(self.btn_redo)
        
        divider1 = QFrame(); divider1.setFrameShape(QFrame.VLine); divider1.setStyleSheet("color: #e2e8f0; margin: 0 4px;")
        self.btn_copy = self.create_icon_btn("fa5s.copy", "Copiar")
        self.btn_paste = self.create_icon_btn("fa5s.paste", "Pegar")
        self.btn_delete = self.create_icon_btn("fa5s.trash-alt", "Eliminar", color="#ef4444", hover_color="#dc2626")
        
        divider2 = QFrame(); divider2.setFrameShape(QFrame.VLine); divider2.setStyleSheet("color: #e2e8f0; margin: 0 4px;")
        self.btn_add_page_header = QPushButton(" Añadir Página")
        self.btn_add_page_header.setIcon(qta.icon('fa5s.plus-circle', color='white'))
        self.btn_add_page_header.setStyleSheet("QPushButton { background-color: #0b50da; color: white; border-radius: 8px; padding: 6px 14px; font-weight: bold; font-size: 13px; border: none; } QPushButton:hover { background-color: #0940b0; }")
        
        right_header.addWidget(ur_container)
        right_header.addWidget(divider1)
        right_header.addWidget(self.btn_copy)
        right_header.addWidget(self.btn_paste)
        right_header.addWidget(self.btn_delete)
        right_header.addWidget(divider2)
        right_header.addWidget(self.btn_add_page_header)
        header_layout.addLayout(right_header)

        # 2. ÁREA CENTRAL (Sidebar + Viewer + Properties)
        middle_widget = QWidget()
        middle_layout = QHBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)

        # SIDEBAR (Material 3 Expressive)
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

        # WORKSPACE
        workspace_container = QWidget()
        workspace_layout = QGridLayout(workspace_container)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        
        self.viewer = PDFViewer(self)
        self.properties_panel = PropertiesPanel(self)
        
        workspace_layout.addWidget(self.viewer, 0, 0)
        workspace_layout.addWidget(self.properties_panel, 0, 1)
        self.properties_panel.hide()

        # Pantalla de Bienvenida
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

        self.status_label = QLabel("✨ Bienvenido a PDFormer")
        self.status_label.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500; border: none;")
        
        nav_controls = QHBoxLayout()
        self.btn_prev = self.create_icon_btn("fa5s.chevron-left", "Anterior")
        self.page_label = QLabel(" Página 0 / 0 ")
        self.page_label.setStyleSheet("background-color: #f1f5f9; color: #334155; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px;")
        self.btn_next = self.create_icon_btn("fa5s.chevron-right", "Siguiente")
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #475569; border: none;")

        nav_controls.addWidget(self.btn_prev)
        nav_controls.addWidget(self.page_label)
        nav_controls.addWidget(self.btn_next)
        nav_controls.addSpacing(16)
        nav_controls.addWidget(self.zoom_label)

        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()
        footer_layout.addLayout(nav_controls)

        main_layout.addWidget(header)
        main_layout.addWidget(middle_widget)
        main_layout.addWidget(footer)

    def create_nav_button(self, text):
        btn = QPushButton(text)
        btn.setStyleSheet("QPushButton { background: transparent; color: #475569; font-weight: 500; font-size: 14px; padding: 6px 12px; border-radius: 6px; border: none; } QPushButton::menu-indicator { image: none; } QPushButton:hover { background: #f1f5f9; color: #0f172a; }")
        return btn

    def create_icon_btn(self, icon_name, tooltip, color="#64748b", hover_color="#0b50da"):
        btn = QPushButton()
        btn.setToolTip(tooltip)
        btn.setFixedSize(32, 32)
        btn.setIcon(qta.icon(icon_name, color=color, color_active=hover_color))
        btn.setIconSize(QSize(18, 18))
        btn.setStyleSheet("QPushButton { background: transparent; border-radius: 6px; border: none; } QPushButton:hover { background: #e2e8f0; }")
        return btn

    def create_floating_btn(self, icon_name, tooltip):
        btn = QPushButton()
        btn.setToolTip(tooltip)
        btn.setFixedSize(48, 48)
        btn.setIcon(qta.icon(icon_name, color="#475569", color_active="#0b50da"))
        btn.setIconSize(QSize(20, 20))
        btn.setStyleSheet("QPushButton { background: white; border-radius: 24px; border: 1px solid #e2e8f0; } QPushButton:hover { background: #f8f9fc; }")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15); shadow.setColor(QColor(0, 0, 0, 25)); shadow.setOffset(0, 4)
        btn.setGraphicsEffect(shadow)
        return btn

    def add_sidebar_section(self, layout, title):
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; letter-spacing: 1px; padding-left: 8px; margin-top: 12px; border: none;")
        layout.addWidget(lbl)

    def add_sidebar_divider(self, layout):
        div = QFrame(); div.setFrameShape(QFrame.HLine); div.setStyleSheet("color: #e2e8f0; margin: 8px 0;"); layout.addWidget(div)

    def add_sidebar_tool(self, layout, tool_id, icon_name, text, is_toggle=False):
        btn = QPushButton(f"  {text}")
        btn.setCheckable(is_toggle)
        btn.setProperty('tool_id', tool_id)
        btn.setProperty('active', False)
        btn.setProperty('icon_name', icon_name)
        btn.setIcon(qta.icon(icon_name, color="#475569"))
        btn.setIconSize(QSize(18, 18))
        btn.setStyleSheet("QPushButton { text-align: left; padding: 10px 14px; border-radius: 8px; background: transparent; color: #475569; font-weight: 500; font-size: 14px; border: none; } QPushButton:hover { background: #e2e8f0; color: #0f172a; } QPushButton[active='true'] { background: #0b50da; color: white; font-weight: bold; }")
        if tool_id == 'snap':
            btn.setChecked(True); btn.setProperty('active', True); btn.setIcon(qta.icon(icon_name, color="#ffffff"))
            btn.clicked.connect(self.toggle_snap)
        else:
            btn.clicked.connect(lambda checked, tid=tool_id: self.set_tool(tid))
        layout.addWidget(btn); self.sidebar_buttons[tool_id] = btn

    def setup_welcome_screen(self, layout):
        self.welcome_widget = QWidget()
        vbox = QVBoxLayout(self.welcome_widget)
        vbox.addStretch()
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)
        
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon('fa5s.file-upload', color='#94a3b8').pixmap(64, 64))
        icon_lbl.setStyleSheet("background-color: #f1f5f9; border-radius: 40px; padding: 20px;")
        icon_lbl.setFixedSize(100, 100)
        
        title = QLabel("Ningún documento abierto")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #0f172a; margin-top: 20px;")
        subtitle = QLabel("Bienvenido a PDFormer. Arrastra y suelta un documento PDF aquí\no usa los botones para empezar.")
        subtitle.setStyleSheet("font-size: 14px; color: #64748b; margin-top: 10px; margin-bottom: 30px;")
        
        btns_layout = QHBoxLayout()
        btn_open = QPushButton("Abrir PDF")
        btn_open.setStyleSheet("QPushButton { background-color: #0b50da; color: white; border-radius: 20px; padding: 10px 24px; font-weight: bold; border: none; } QPushButton:hover { background-color: #0940b0; }")
        btn_open.clicked.connect(self.open_pdf)
        btn_new = QPushButton("Nuevo en blanco")
        btn_new.setStyleSheet("QPushButton { background-color: #f1f5f9; color: #334155; border-radius: 20px; padding: 10px 24px; font-weight: bold; border: none; } QPushButton:hover { background-color: #e2e8f0; }")
        btn_new.clicked.connect(self.new_pdf)
        
        btns_layout.addWidget(btn_open); btns_layout.addSpacing(15); btns_layout.addWidget(btn_new)
        center_layout.addWidget(icon_lbl, 0, Qt.AlignCenter); center_layout.addWidget(title, 0, Qt.AlignCenter); center_layout.addWidget(subtitle, 0, Qt.AlignCenter); center_layout.addLayout(btns_layout)
        vbox.addWidget(center_widget); vbox.addStretch()
        layout.addWidget(self.welcome_widget, 0, 0)

    def update_ui_state(self):
        has_doc = self.doc is not None
        self.welcome_widget.setVisible(not has_doc)
        self.viewer.setVisible(has_doc)
        self.floating_container.setVisible(has_doc)

    def close_document(self):
        if self.doc: self.doc.close(); self.doc = None
        self.current_file_path = None; self.current_page = 0; self.all_fields.clear(); self.undo_stack.clear(); self.viewer.scene.clear()
        self.zoom = 1.0; self.viewer.setTransform(QTransform()); self.zoom_label.setText("100%")
        self.update_ui_state(); self.update_page_label()

    def setup_actions(self):
        # Menú Archivo
        menu_file = QMenu(self)
        menu_file.addAction(qta.icon('fa5s.file-alt'), "Nuevo PDF", self.new_pdf, "Ctrl+N")
        menu_file.addAction(qta.icon('fa5s.folder-open'), "Abrir PDF", self.open_pdf, "Ctrl+O")
        menu_file.addAction(qta.icon('fa5s.save'), "Guardar", self.save_pdf, "Ctrl+S")
        menu_file.addAction(qta.icon('fa5s.download'), "Guardar como...", self.save_pdf_as, "Ctrl+Shift+S")
        self.btn_file.setMenu(menu_file)

        # Menú Edición
        menu_edit = QMenu(self)
        menu_edit.addAction(qta.icon('fa5s.undo-alt'), "Deshacer", self.undo_stack.undo, "Ctrl+Z")
        menu_edit.addAction(qta.icon('fa5s.redo-alt'), "Rehacer", self.undo_stack.redo, "Ctrl+Y")
        menu_edit.addAction(qta.icon('fa5s.copy'), "Copiar", self.copy_field, "Ctrl+C")
        menu_edit.addAction(qta.icon('fa5s.paste'), "Pegar", self.paste_field, "Ctrl+V")
        menu_edit.addAction(qta.icon('fa5s.trash-alt'), "Eliminar", self.delete_selected_field, "Del")
        self.btn_edit.setMenu(menu_edit)

        # Menú Páginas
        menu_pages = QMenu(self)
        menu_pages.addAction(qta.icon('fa5s.plus'), "Añadir Página", self.add_blank_page)
        menu_pages.addAction(qta.icon('fa5s.trash'), "Borrar Página", self.delete_current_page)
        self.btn_pages.setMenu(menu_pages)

        # Conexiones Header
        self.btn_undo.clicked.connect(self.undo_stack.undo); self.btn_redo.clicked.connect(self.undo_stack.redo)
        self.btn_copy.clicked.connect(self.copy_field); self.btn_paste.clicked.connect(self.paste_field); self.btn_delete.clicked.connect(self.delete_selected_field)
        self.btn_add_page_header.clicked.connect(self.add_blank_page)

        # Conexiones Footer
        self.btn_prev.clicked.connect(self.prev_page); self.btn_next.clicked.connect(self.next_page)
        self.btn_zoom_in.clicked.connect(self.zoom_in); self.btn_zoom_out.clicked.connect(self.zoom_out); self.btn_fit_width.clicked.connect(self.fit_to_width)

        # Feedback de Selección
        self.viewer.scene.selectionChanged.connect(self.on_selection_changed)

    def on_selection_changed(self):
        sel = self.viewer.scene.selectedItems()
        if len(sel) == 1 and isinstance(sel[0], FieldItem): self.properties_panel.set_item(sel[0])
        else: self.properties_panel.set_item(None)

    def toggle_snap(self, checked):
        self.snap_enabled = checked
        btn = self.sidebar_buttons['snap']; btn.setProperty('active', checked)
        btn.style().unpolish(btn); btn.style().polish(btn)
        btn.setIcon(qta.icon(btn.property('icon_name'), color="#ffffff" if checked else "#475569"))

    def set_tool(self, tool_id):
        self.current_tool = None if tool_id == 'cursor' else tool_id
        self.viewer.setCursor(Qt.ArrowCursor if tool_id == 'cursor' else Qt.CrossCursor)
        if self.current_tool: self.viewer.scene.clearSelection()
        
        for tid, btn in self.sidebar_buttons.items():
            if tid == 'snap': continue 
            active = (tid == tool_id)
            btn.setProperty('active', active); btn.style().unpolish(btn); btn.style().polish(btn)
            btn.setIcon(qta.icon(btn.property('icon_name'), color="#ffffff" if active else "#475569"))

    def new_pdf(self):
        self.doc = fitz.open(); self.doc.new_page(width=595, height=842); self.current_page = 0; self.all_fields.clear(); self.undo_stack.clear()
        self.zoom = 1.0; self.viewer.setTransform(QTransform()); self.render_document(); self.update_page_label(); self.update_ui_state()

    def open_pdf(self):
        fp, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "PDF (*.pdf)")
        if fp: self.load_pdf(fp)

    def load_pdf(self, fp):
        try:
            with open(fp, "rb") as f: self.doc = fitz.open("pdf", f.read())
            self.current_file_path = fp; self.current_page = 0; self.all_fields.clear(); self.undo_stack.clear()
            self.zoom = 1.0; self.viewer.setTransform(QTransform()); self.render_document(); self.update_page_label(); self.update_ui_state()
            self.setWindowTitle(f"PDFormer - {os.path.basename(fp)}")
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def zoom_in(self): self.zoom = min(self.zoom * 1.15, 3.0); self.apply_zoom()
    def zoom_out(self): self.zoom = max(self.zoom / 1.15, 0.5); self.apply_zoom()
    def fit_to_width(self):
        if not self.doc: return
        self.zoom = (self.viewer.viewport().width() - 40) / self.doc[0].rect.width
        self.apply_zoom()
    def apply_zoom(self): self.viewer.setTransform(QTransform().scale(self.zoom, self.zoom)); self.zoom_label.setText(f"{int(self.zoom * 100)}%")

    def add_blank_page(self):
        if not self.doc: return self.new_pdf()
        self.doc.new_page(pno=self.current_page + 1); self.render_document(); self.update_page_label()

    def delete_current_page(self):
        if self.doc and len(self.doc) > 1: self.doc.delete_page(self.current_page); self.render_document(); self.update_page_label()

    def create_field(self, rect):
        item = FieldItem(rect, self.current_tool, f"Campo_{int(time.time())}")
        self.undo_stack.push(AddFieldCommand(self.viewer.scene, item, self.all_fields)); self.set_tool('cursor')

    def delete_selected_field(self):
        for i in self.viewer.scene.selectedItems():
            if isinstance(i, FieldItem): self.undo_stack.push(RemoveFieldCommand(self.viewer.scene, i, self.all_fields))

    def copy_field(self):
        sel = self.viewer.scene.selectedItems()
        if sel and isinstance(sel[0], FieldItem):
            i = sel[0]; self.copied_field_data = {'type': i.field_type, 'rect': i.rect(), 'options': i.options, 'has_border': i.has_border, 'text_content': i.text_content}

    def paste_field(self):
        if self.copied_field_data:
            d = self.copied_field_data
            item = FieldItem(d['rect'].translated(20, 20), d['type'], f"Copia_{int(time.time())}", d['options'], d['has_border'], d['text_content'])
            self.undo_stack.push(AddFieldCommand(self.viewer.scene, item, self.all_fields))

    def prev_page(self):
        if self.current_page > 0: self.current_page -= 1; self.viewer.verticalScrollBar().setValue(int(self.page_rects[self.current_page].top())); self.update_page_label()
    def next_page(self):
        if self.current_page < len(self.doc) - 1: self.current_page += 1; self.viewer.verticalScrollBar().setValue(int(self.page_rects[self.current_page].top())); self.update_page_label()

    def update_page_label(self):
        if not self.doc: return
        vc = self.viewer.mapToScene(self.viewer.viewport().rect().center()).y()
        for p, r in self.page_rects.items():
            if r.top() <= vc <= r.bottom() + 30: self.current_page = p; break
        self.page_label.setText(f" Página {self.current_page + 1} / {len(self.doc)} ")

    def render_document(self):
        if not self.doc: return
        self.viewer.scene.clear(); self.page_rects.clear(); cy = 0
        for p in range(len(self.doc)):
            page = self.doc[p]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), annots=True)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            bg = self.viewer.scene.addPixmap(QPixmap.fromImage(img))
            bg.setScale(0.5); bg.setPos(0, cy); bg.setZValue(-1)
            sh = QGraphicsDropShadowEffect(); sh.setBlurRadius(20); sh.setColor(QColor(0,0,0,30)); bg.setGraphicsEffect(sh)
            self.page_rects[p] = QRectF(0, cy, page.rect.width, page.rect.height)
            cy += page.rect.height + 30
        self.viewer.setSceneRect(self.viewer.scene.itemsBoundingRect())
        for i in self.all_fields: self.viewer.scene.addItem(i); i.show()

    def save_pdf(self): return self._perform_save(self.current_file_path) if self.current_file_path else self.save_pdf_as()
    def save_pdf_as(self):
        fp, _ = QFileDialog.getSaveFileName(self, "Guardar", "", "PDF (*.pdf)")
        if fp: return self._perform_save(fp)
        return False

    def _perform_save(self, fp):
        try:
            exp = fitz.open("pdf", self.doc.write())
            for i in self.all_fields:
                if i.scene() is None: continue
                cy = i.sceneBoundingRect().center().y(); target = 0
                for p, r in self.page_rects.items():
                    if r.top() <= cy <= r.bottom() + 30: target = p; break
                page = exp[target]; pr = self.page_rects[target]; rect = i.sceneBoundingRect()
                fr = fitz.Rect(rect.left()-pr.left(), rect.top()-pr.top(), rect.right()-pr.left(), rect.bottom()-pr.top())
                if i.field_type == 'whiteout': page.draw_rect(fr, color=(1,1,1), fill=(1,1,1))
                elif i.field_type == 'static_text': page.insert_textbox(fr, i.text_content, fontsize=11, fontname="helv")
                else:
                    w = fitz.Widget(); w.rect = fr; w.field_name = i.field_name
                    if i.field_type == 'text': w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                    elif i.field_type == 'textarea': w.field_type = fitz.PDF_WIDGET_TYPE_TEXT; w.field_flags |= 4096
                    elif i.field_type == 'checkbox': w.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                    elif i.field_type == 'dropdown': w.field_type = fitz.PDF_WIDGET_TYPE_COMBOBOX; w.choice_values = i.options
                    elif i.field_type == 'signature': w.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
                    page.add_widget(w)
            exp.save(fp, deflate=True, garbage=4, clean=True); exp.close(); self.undo_stack.setClean(); return True
        except Exception as e: QMessageBox.critical(self, "Error", str(e)); return False

if __name__ == '__main__':
    app = QApplication(sys.argv); editor = PDFFormEditor(); editor.show(); sys.exit(app.exec_())
