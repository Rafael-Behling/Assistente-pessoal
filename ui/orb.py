import sys
import math
import time
import random
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QRegion, QShortcut, QKeySequence

sys.path.append(str(Path(__file__).parent.parent))
from core.brain import Brain
from core.vad import VADListener
from core.global_hotkey import GlobalHotkey


class OrbWidget(QWidget):
    state_signal = pyqtSignal(str)
    close_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(60, 60)
        self.setGeometry(0, 0, 60, 60)
        self.move(0, 0)

        self.setMask(QRegion(0, 0, 60, 60, QRegion.RegionType.Ellipse))

        self.base_radius = 18
        self.radius = self.base_radius
        self.target_radius = self.base_radius
        self.pulse_speed = 0.4
        self.color = QColor(0, 191, 255)

        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.update_pulse)
        self.pulse_timer.start(30)

        self.state = "listening"
        self.processing = False
        self.brain = Brain()
        self.state_signal.connect(self.set_state)

        self.close_requested.connect(self.close, Qt.ConnectionType.QueuedConnection)
        self.local_close = QShortcut(QKeySequence("Ctrl+E"), self)
        self.local_close.activated.connect(self.close)

        self.hotkey = GlobalHotkey(self.close_requested.emit)
        try:
            self.hotkey.start()
        except Exception as e:
            print(f"[ORB] Atalho global indisponível: {e}")

        self.vad = VADListener(self.brain.config, self.on_utterance)
        try:
            self.vad.start()
            print("[ORB] Microfone aberto - fale quando quiser")
        except Exception as e:
            print(f"[ORB] Erro ao abrir microfone: {e}")

        os.system('niri msg action move-floating-window -x 0 -y 0 >/dev/null 2>&1 &')

    def set_state(self, state):
        self.state = state
        if state == "listening":
            self.color = QColor(0, 191, 255)
        elif state == "thinking":
            self.color = QColor(255, 165, 0)
        elif state == "speaking":
            self.color = QColor(0, 255, 127)
        else:
            self.color = QColor(0, 191, 255)
            self.state = "idle"

    def on_utterance(self, audio_path):
        if self.processing:
            return
        self.processing = True
        try:
            self.state_signal.emit("thinking")
            text = self.brain.transcribe_audio(audio_path)
            if not text:
                self.state_signal.emit("listening")
                return

            response = self.brain.think(text)
            self.brain.log_turn(text, response)

            self.state_signal.emit("speaking")
            self.brain.speak(response)
        except Exception as e:
            print(f"[ORB] Erro no processamento: {e}")
        finally:
            self.processing = False
            self.state_signal.emit("listening")

    def update_pulse(self):
        t = time.monotonic()
        if self.state == "idle":
            self.target_radius = self.base_radius + math.sin(t * 2.0) * 1.5
        elif self.state == "listening":
            self.target_radius = self.base_radius + random.randint(-2, 2)
        elif self.state == "speaking":
            self.target_radius = self.base_radius + random.randint(-4, 4)
        elif self.state == "thinking":
            self.target_radius = self.base_radius + math.sin(t * 4.0) * 3
        else:
            self.target_radius = self.base_radius

        if self.radius < self.target_radius:
            self.radius += self.pulse_speed
        elif self.radius > self.target_radius:
            self.radius -= self.pulse_speed

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        cx = self.width() // 2
        cy = self.height() // 2

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        glow = QColor(self.color)
        glow.setAlpha(35)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(cx - int(self.radius + 6), cy - int(self.radius + 6), int((self.radius + 6) * 2), int((self.radius + 6) * 2))

        painter.setBrush(QBrush(self.color))
        painter.drawEllipse(cx - int(self.radius), cy - int(self.radius), int(self.radius * 2), int(self.radius * 2))

        highlight = QColor(255, 255, 255)
        highlight.setAlpha(70)
        painter.setBrush(QBrush(highlight))
        r = self.radius * 0.22
        painter.drawEllipse(cx - int(self.radius * 0.6), cy - int(self.radius * 0.6), int(r * 2), int(r * 2))

    def closeEvent(self, event):
        print("[ORB] Fechando...")
        self.hotkey.stop()
        self.vad.stop()
        event.accept()
        QApplication.instance().quit()


def main():
    app = QApplication(sys.argv)
    orb = OrbWidget()
    orb.show()
    orb.move(0, 0)
    orb.setGeometry(0, 0, 60, 60)
    app.processEvents()
    orb.move(0, 0)
    orb.setGeometry(0, 0, 60, 60)
    os.system('niri msg action move-floating-window -x 0 -y 0 >/dev/null 2>&1 &')
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
