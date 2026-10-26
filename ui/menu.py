import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QListWidget, QListWidgetItem,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

sys.path.append(str(Path(__file__).parent.parent))
from core.tts import TTS

class VoiceMenu(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sexta-Feira - Configuração")
        self.setFixedSize(400, 500)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        
        self.tts = TTS()
        self.selected_voice = None
        self.voices = []
        
        layout = QVBoxLayout()
        
        title = QLabel("Sexta-Feira")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Escolha a voz da sua assistente")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        self.voice_list = QListWidget()
        self.voice_list.itemClicked.connect(self.on_voice_selected)
        layout.addWidget(self.voice_list)
        
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("Testar Voz")
        self.test_btn.clicked.connect(self.test_voice)
        self.test_btn.setEnabled(False)
        btn_layout.addWidget(self.test_btn)
        
        self.start_btn = QPushButton("Iniciar")
        self.start_btn.clicked.connect(self.start_assistant)
        self.start_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        self.load_voices()
        
    def load_voices(self):
        self.voice_list.clear()
        self.voices = self.tts.list_voices()
        if not self.voices:
            item = QListWidgetItem("edge-tts não disponível ou sem vozes")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.voice_list.addItem(item)
            return
        
        pt_voices = [v for v in self.voices if v.get('Locale', '').startswith('pt')]
        other_voices = [v for v in self.voices if not v.get('Locale', '').startswith('pt')]
        
        for voice in pt_voices + other_voices:
            locale = voice.get('Locale', '')
            name = voice.get('ShortName', '')
            gender = voice.get('Gender', '')
            display = f"[{locale}] {name} ({gender})"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, voice.get('ShortName'))
            self.voice_list.addItem(item)
        
    def on_voice_selected(self, item):
        self.selected_voice = item.data(Qt.ItemDataRole.UserRole)
        if self.selected_voice:
            self.test_btn.setEnabled(True)
            self.start_btn.setEnabled(True)
        
    def test_voice(self):
        if self.selected_voice:
            self.test_btn.setEnabled(False)
            self.test_btn.setText("Testando...")
            QApplication.processEvents()
            try:
                self.tts.speak("Olá, eu sou a Sexta-Feira. Pronta para te ajudar.", self.selected_voice)
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))
            self.test_btn.setText("Testar Voz")
            self.test_btn.setEnabled(True)
        
    def start_assistant(self):
        if self.selected_voice:
            config_path = Path(__file__).parent.parent / "config.json"
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                config['voice'] = self.selected_voice
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))
                return
            
            self.close()
            self.start_orb()
        
    def start_orb(self):
        import subprocess
        subprocess.Popen([sys.executable, "-u", str(Path(__file__).parent / "orb.py")], cwd=str(Path(__file__).parent.parent))

def main():
    app = QApplication(sys.argv)
    menu = VoiceMenu()
    menu.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
