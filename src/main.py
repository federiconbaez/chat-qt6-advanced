import sys
import os
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QListWidget, QSplitter, QMenuBar, QMenu, QLabel,
                             QFileDialog, QColorDialog, QSystemTrayIcon, QComboBox,
                             QListWidgetItem, QScrollArea)
from PySide6.QtCore import Qt, QSize, Signal, QTimer, QMimeData
from PySide6.QtGui import (QColor, QPalette, QFont, QIcon, QPixmap, QImage,
                          QDrag, QTextCharFormat, QTextCursor, QTextImageFormat)
from PySide6.QtCore import QObject, QEvent


class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"

@dataclass
class Message:
    content: str
    type: MessageType
    sender: str
    timestamp: datetime
    metadata: Optional[dict] = None

class Theme:
    def __init__(self, name: str, colors: dict):
        self.name = name
        self.colors = colors

class Themes:
    DARK = Theme("Dark", {
        "background": "#36393F",
        "secondary": "#2F3136",
        "accent": "#7289DA",
        "text": "#FFFFFF",
        "input": "#40444B",
        "hover": "#677BC4",
        "pressed": "#5B6EAE"
    })
    
    LIGHT = Theme("Light", {
        "background": "#FFFFFF",
        "secondary": "#F2F3F5",
        "accent": "#5865F2",
        "text": "#2E3338",
        "input": "#EBEDEF",
        "hover": "#4752C4",
        "pressed": "#3C45A5"
    })
    
    NORD = Theme("Nord", {
        "background": "#2E3440",
        "secondary": "#3B4252",
        "accent": "#88C0D0",
        "text": "#ECEFF4",
        "input": "#434C5E",
        "hover": "#81A1C1",
        "pressed": "#5E81AC"
    })

class EmojiPanel(QWidget):
    emoji_selected = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.setup_ui()
        
    def setup_ui(self):
        self.emoji_grid = QWidget()
        grid_layout = QVBoxLayout(self.emoji_grid)
        
        # Común conjunto de emojis
        emojis = ["😀", "😂", "🤣", "😊", "😍", "🤔", "😎", "😭", "👍", "❤️",
                  "🎉", "✨", "🔥", "💯", "🙏", "👏", "🤝", "💪", "🌟", "⭐"]
        
        for i in range(0, len(emojis), 5):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            for emoji in emojis[i:i+5]:
                btn = QPushButton(emoji)
                btn.setFixedSize(40, 40)
                btn.clicked.connect(lambda checked, e=emoji: self.emoji_selected.emit(e))
                row_layout.addWidget(btn)
            grid_layout.addWidget(row_widget)
        
        scroll = QScrollArea()
        scroll.setWidget(self.emoji_grid)
        scroll.setWidgetResizable(True)
        self.layout.addWidget(scroll)

class ChatMessageWidget(QWidget):
    def __init__(self, message: Message, theme: Theme):
        super().__init__()
        self.message = message
        self.theme = theme
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header (sender + timestamp)
        header = QHBoxLayout()
        sender = QLabel(self.message.sender)
        sender.setStyleSheet(f"color: {self.theme.colors['accent']}; font-weight: bold;")
        timestamp = QLabel(self.message.timestamp.strftime("%H:%M"))
        timestamp.setStyleSheet(f"color: {self.theme.colors['text']}; font-size: 10px;")
        header.addWidget(sender)
        header.addWidget(timestamp)
        header.addStretch()
        layout.addLayout(header)
        
        # Content
        if self.message.type == MessageType.TEXT:
            content = QLabel(self.message.content)
            content.setWordWrap(True)
            content.setStyleSheet(f"color: {self.theme.colors['text']};")
        elif self.message.type == MessageType.IMAGE:
            content = QLabel()
            pixmap = QPixmap(self.message.content)
            content.setPixmap(pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            content = QLabel(f"📎 {os.path.basename(self.message.content)}")
            content.setStyleSheet(f"color: {self.theme.colors['accent']};")
        
        layout.addWidget(content)
        
        self.setStyleSheet(f"""
            ChatMessageWidget {{
                background-color: {self.theme.colors['secondary']};
                border-radius: 10px;
                padding: 10px;
                margin: 5px;
            }}
        """)

class ModernChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_theme = Themes.DARK
        self.messages: List[Message] = []
        self.setup_ui()
        self.setup_tray()
        self.setup_shortcuts()
        
    def setup_ui(self):
        self.setWindowTitle("Chat")
        self.setMinimumSize(1000, 700)
        
        # Menú
        self.create_menu()
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Splitter principal
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # Panel izquierdo
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Buscador de contactos
        self.contact_search = QLineEdit()
        self.contact_search.setPlaceholderText("Buscar contactos...")
        self.contact_search.textChanged.connect(self.filter_contacts)
        left_layout.addWidget(self.contact_search)
        
        # Lista de contactos
        self.contacts_list = QListWidget()
        self.setup_contacts()
        left_layout.addWidget(self.contacts_list)
        
        # Panel de chat
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        
        # Información del chat actual
        chat_info = QWidget()
        chat_info_layout = QHBoxLayout(chat_info)
        self.chat_name = QLabel("Chat General")
        self.chat_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.online_status = QLabel("• En línea")
        self.online_status.setStyleSheet("color: #43B581;")
        chat_info_layout.addWidget(self.chat_name)
        chat_info_layout.addWidget(self.online_status)
        chat_info_layout.addStretch()
        chat_layout.addWidget(chat_info)
        
        # Área de mensajes
        self.messages_area = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_area)
        self.messages_layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setWidget(self.messages_area)
        scroll.setWidgetResizable(True)
        chat_layout.addWidget(scroll)
        
        # Panel de entrada
        input_panel = QWidget()
        input_layout = QVBoxLayout(input_panel)
        
        # Área de escritura
        message_input_container = QWidget()
        message_input_layout = QHBoxLayout(message_input_container)
        
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Escribe un mensaje...")
        self.message_input.setMaximumHeight(100)
        
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        
        # Botones de acción
        emoji_btn = QPushButton("😊")
        file_btn = QPushButton("📎")
        self.send_button = QPushButton("Enviar")
        
        buttons_layout.addWidget(emoji_btn)
        buttons_layout.addWidget(file_btn)
        buttons_layout.addWidget(self.send_button)
        
        message_input_layout.addWidget(self.message_input)
        message_input_layout.addWidget(buttons_widget)
        
        # Panel de emojis (oculto por defecto)
        self.emoji_panel = EmojiPanel()
        self.emoji_panel.hide()
        self.emoji_panel.emoji_selected.connect(self.insert_emoji)
        input_layout.addWidget(self.emoji_panel)
        input_layout.addWidget(message_input_container)
        
        chat_layout.addWidget(input_panel)
        
        # Agregar paneles al splitter
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(chat_widget)
        self.main_splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(self.main_splitter)
        
        # Conectar señales
        self.send_button.clicked.connect(self.send_message)
        emoji_btn.clicked.connect(self.toggle_emoji_panel)
        file_btn.clicked.connect(self.select_file)
        self.message_input.installEventFilter(self)
        
        # Aplicar tema inicial
        self.apply_theme(self.current_theme)
    
    def create_menu(self):
        menubar = self.menuBar()
        
        # Menú Archivo
        file_menu = menubar.addMenu("Archivo")
        save_chat = file_menu.addAction("Guardar chat")
        save_chat.triggered.connect(self.save_chat_history)
        
        # Menú Ver
        view_menu = menubar.addMenu("Ver")
        theme_menu = view_menu.addMenu("Temas")
        
        themes = [Themes.DARK, Themes.LIGHT, Themes.NORD]
        for theme in themes:
            action = theme_menu.addAction(theme.name)
            action.triggered.connect(lambda checked, t=theme: self.apply_theme(t))
    
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))  # Necesitarías un archivo de icono
        self.tray_icon.setVisible(True)
    
    def setup_shortcuts(self):
        # Implementar atajos de teclado
        pass
    
    def setup_contacts(self):
        contacts = [
            ("Usuario 1", True),
            ("Usuario 2", False),
            ("Grupo 1", True),
            ("Usuario 3", True)
        ]
        
        for name, online in contacts:
            item = QListWidgetItem()
            widget = QWidget()
            layout = QHBoxLayout(widget)
            
            label = QLabel(name)
            status = QLabel("•")
            status.setStyleSheet(f"color: {'#43B581' if online else '#747F8D'};")
            
            layout.addWidget(status)
            layout.addWidget(label)
            layout.addStretch()
            
            item.setSizeHint(widget.sizeHint())
            self.contacts_list.addItem(item)
            self.contacts_list.setItemWidget(item, widget)
    
    def filter_contacts(self, text):
        for i in range(self.contacts_list.count()):
            item = self.contacts_list.item(i)
            widget = self.contacts_list.itemWidget(item)
            label = widget.findChild(QLabel)
            item.setHidden(text.lower() not in label.text().lower())
    
    def apply_theme(self, theme: Theme):
        self.current_theme = theme
        
        # Aplicar estilos generales
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {theme.colors['background']};
                color: {theme.colors['text']};
            }}
            
            QLineEdit, QTextEdit {{
                background-color: {theme.colors['input']};
                border-radius: 20px;
                padding: 10px;
                color: {theme.colors['text']};
            }}
            
            QPushButton {{
                background-color: {theme.colors['accent']};
                border-radius: 20px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: {theme.colors['hover']};
            }}
            
            QPushButton:pressed {{
                background-color: {theme.colors['pressed']};
            }}
            
            QListWidget {{
                background-color: {theme.colors['secondary']};
                border-radius: 10px;
                padding: 5px;
            }}
            
            QListWidget::item:hover {{
                background-color: {theme.colors['input']};
            }}
            
            QListWidget::item:selected {{
                background-color: {theme.colors['accent']};
            }}
            
            QScrollArea {{
                border: none;
            }}
        """)
        
        # Actualizar mensajes existentes
        self.refresh_messages()
    
    def toggle_emoji_panel(self):
        self.emoji_panel.setVisible(not self.emoji_panel.isVisible())
    
    def insert_emoji(self, emoji: str):
        self.message_input.insertPlainText(emoji)
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo")
        if file_path:
            self.add_message(Message(
                content=file_path,
                type=MessageType.FILE if not file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) 
                     else MessageType.IMAGE,
                sender="Tú",
                timestamp=datetime.now()
            ))
    
    def add_message(self, message: Message):
        self.messages.append(message)
        message_widget = ChatMessageWidget(message, self.current_theme)
        self.messages_layout.addWidget(message_widget)
    
    def send_message(self):
        text = self.message_input.toPlainText().strip()
        if text:
            message = Message(
                content=text,
                type=MessageType.TEXT,
                sender="Tú",
                timestamp=datetime.now()
            )
            self.add_message(message)
            self.message_input.clear()
            
            # Simular respuesta automática
            QTimer.singleShot(1000, self.simulate_response)
    
    def simulate_response(self):
        responses = [
            "¡Interesante punto de vista!",
            "Entiendo lo que dices.",
            "¿Podrías explicar más sobre eso?",
            "Me parece una buena idea.",
            "¿Qué más piensas al respecto?"
        ]
        import random
        response = random.choice(responses)
        
        message = Message(
            content=response,
            type=MessageType.TEXT,
            sender="Usuario 1",
            timestamp=datetime.now()
        )
        self.add_message(message)
        
        # Mostrar notificación
        self.tray_icon.showMessage(
            "Nuevo mensaje",
            f"Usuario 1: {response}",
            QSystemTrayIcon.Information,
            2000
        )
    
    def refresh_messages(self):
        # Limpiar y recrear todos los mensajes con el tema actual
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for message in self.messages:
            message_widget = ChatMessageWidget(message, self.current_theme)
            self.messages_layout.insertWidget(self.messages_layout.count() - 1, message_widget)
    
    def save_chat_history(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar historial",
            "",
            "Archivos de texto (*.txt);;Archivos HTML (*.html)"
        )
        
        if not file_path:
            return
            
        if file_path.endswith('.txt'):
            with open(file_path, 'w', encoding='utf-8') as f:
                for message in self.messages:
                    f.write(f"[{message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
                           f"{message.sender}: {message.content}\n")
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("<html><body style='font-family: Arial, sans-serif;'>")
                for message in self.messages:
                    f.write(f"<div style='margin: 10px; padding: 10px; "
                           f"background-color: {self.current_theme.colors['secondary']};'>"
                           f"<strong style='color: {self.current_theme.colors['accent']};'>"
                           f"{message.sender}</strong> "
                           f"<span style='color: #999; font-size: 0.8em;'>"
                           f"{message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</span><br>"
                           f"<span style='color: {self.current_theme.colors['text']};'>"
                           f"{message.content}</span></div>")
                f.write("</body></html>")
    
    def eventFilter(self, obj: QObject, event: QEvent):
        if obj == self.message_input and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_Return and key_event.modifiers() == Qt.ControlModifier:
                self.send_message()
                return True
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        # Minimizar a la bandeja del sistema en lugar de cerrar
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()

def main():
    app = QApplication(sys.argv)
    
    # Configurar la fuente predeterminada
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = ModernChatWindow()
    window.show()
    
    # Mensaje de bienvenida
    welcome_message = Message(
        content="¡Bienvenido al chat! Este es un mensaje de sistema.",
        type=MessageType.SYSTEM,
        sender="Sistema",
        timestamp=datetime.now()
    )
    window.add_message(welcome_message)
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()