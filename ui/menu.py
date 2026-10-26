import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QListWidget, QListWidgetItem,
    QMessageBox, QFormLayout, QLineEdit, QSpinBox, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

sys.path.append(str(Path(__file__).parent.parent))
from core.tts import TTS

CONFIG_PATH = Path(__file__).parent.parent / "config.json"


class VoiceMenu(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sexta-Feira - Configuração")
        self.setFixedSize(420, 700)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        self.tts = TTS()
        self.selected_voice = None
        self.voices = []

        layout = QVBoxLayout()

        title = QLabel("Sexta-Feira")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Escolha a voz e ajuste as opções")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        self.voice_list = QListWidget()
        self.voice_list.setMaximumHeight(140)
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

        settings_group = QGroupBox("Configurações")
        form = QFormLayout()
        settings_group.setLayout(form)

        self.wake_combo = QComboBox()
        self.wake_combo.addItems(['wake_word', 'always_on'])
        form.addRow("Ativação:", self.wake_combo)

        self.wake_edit = QLineEdit()
        form.addRow("Nome (vírgula p/ separar):", self.wake_edit)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setSuffix(" s")
        form.addRow("Sessão sem falar:", self.timeout_spin)

        self.vad_combo = QComboBox()
        self.vad_combo.addItems(['energy', 'silero'])
        form.addRow("Detecção de fala:", self.vad_combo)

        self.stt_combo = QComboBox()
        self.stt_combo.addItems(['tiny', 'base', 'small', 'medium'])
        form.addRow("Modelo Whisper:", self.stt_combo)

        self.weather_edit = QLineEdit()
        self.weather_edit.setPlaceholderText("vazio = pela sua região (IP)")
        form.addRow("Cidade (clima):", self.weather_edit)

        self.llm_combo = QComboBox()
        self.llm_combo.addItems(['local', 'api'])
        form.addRow("Inteligência:", self.llm_combo)

        self.save_btn = QPushButton("Salvar Configurações")
        self.save_btn.clicked.connect(self.save_settings)
        form.addRow(self.save_btn)

        layout.addWidget(settings_group)
        self.setLayout(layout)

        self.load_settings()
        self.load_voices()

    def load_settings(self):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            config = {}
        act = config.get('activation', {})
        self.wake_combo.setCurrentText(act.get('mode', 'wake_word'))
        self.wake_edit.setText(', '.join(act.get('wake_words', ['sexta feira'])))
        self.timeout_spin.setValue(int(act.get('session_timeout_s', 20)))
        self.vad_combo.setCurrentText(config.get('vad', {}).get('engine', 'energy'))
        self.stt_combo.setCurrentText(config.get('stt', {}).get('model', 'small'))
        self.weather_edit.setText((config.get('weather') or {}).get('location', ''))
        self.llm_combo.setCurrentText(config.get('llm', {}).get('mode', 'local'))

    def save_settings(self):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            config = {}
        wake_words = [w.strip() for w in self.wake_edit.text().split(',') if w.strip()]
        config.setdefault('activation', {})
        config['activation']['mode'] = self.wake_combo.currentText()
        if wake_words:
            config['activation']['wake_words'] = wake_words
        config['activation']['session_timeout_s'] = self.timeout_spin.value()
        config.setdefault('vad', {})
        config['vad']['engine'] = self.vad_combo.currentText()
        config.setdefault('stt', {})
        config['stt']['model'] = self.stt_combo.currentText()
        config.setdefault('weather', {})
        config['weather']['location'] = self.weather_edit.text().strip()
        config.setdefault('llm', {})
        config['llm']['mode'] = self.llm_combo.currentText()
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, "Erro", str(e))
            return
        QMessageBox.information(self, "Salvo", "Configurações salvas.")

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
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                config['voice'] = self.selected_voice
                with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
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
