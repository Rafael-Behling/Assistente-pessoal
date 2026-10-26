import sys
import math
import time
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QBrush, QPen, QShortcut, QKeySequence

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
        self.setFixedSize(110, 110)
        self.setGeometry(0, 0, 110, 110)
        self.move(0, 0)

        self.base_radius = 15
        self.radius = self.base_radius
        self.target_radius = self.base_radius
        self.level = 0.0
        self.wobble = 0.8
        self.dimmed = False
        self._speaking_started = False
        self.t0 = time.monotonic()
        self._last_ripple = 0.0
        self.ripples = []
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
        self._speaking_started = False
        try:
            self.state_signal.emit("thinking")
            outcome = self.brain.handle_utterance(audio_path, on_sentence=self._on_sentence)
            if outcome is None:
                return
            transcript, query, response = outcome
            self.brain.log_turn(transcript, response)

            if not self._speaking_started:
                self.state_signal.emit("speaking")
                self.brain.speak(response)
        except Exception as e:
            print(f"[ORB] Erro no processamento: {e}")
        finally:
            self.processing = False
            self.state_signal.emit("listening")

    def _on_sentence(self, sentence):
        if not self._speaking_started:
            self._speaking_started = True
            self.state_signal.emit("speaking")
        self.brain.speak(sentence)

    def update_pulse(self):
        t = time.monotonic() - self.t0
        target = self.base_radius
        wobble_target = 0.8

        if self.state == "idle":
            target += math.sin(t * 1.5) * 1.0
            wobble_target = 0.5
        elif self.state == "listening":
            raw = getattr(self.vad, 'current_rms', 0.0) or 0.0
            lvl = max(0.0, min(1.0, (raw - 0.002) / 0.03))
            self.level += (lvl - self.level) * 0.3
            self.dimmed = not self.brain.session_open()
            base = 11 if self.dimmed else self.base_radius
            target = base + self.level * 9.0 + math.sin(t * 2.0) * (0.5 if self.dimmed else 0.8)
            wobble_target = 0.35 if self.dimmed else 0.8 + self.level * 1.2
        elif self.state == "thinking":
            self.dimmed = False
            target += math.sin(t * 3.0) * 2.0
            wobble_target = 2.0
        elif self.state == "speaking":
            self.dimmed = False
            target += math.sin(t * 4.5) * 1.5
            wobble_target = 1.4
            if t - self._last_ripple > 0.3:
                self._last_ripple = t
                self.ripples.append([self.radius, 130.0])

        self.radius += (target - self.radius) * 0.35
        self.wobble += (wobble_target - self.wobble) * 0.15

        for ripple in self.ripples:
            ripple[0] += 1.4
            ripple[1] -= 4.5
        self.ripples = [r for r in self.ripples if r[1] > 0]

        self.update()

    def _blob_path(self, radius, t, wobble):
        path = QPainterPath()
        steps = 48
        harmonics = ((3, 0.055, 1.1), (5, 0.035, 1.9), (7, 0.02, 2.6))
        speed = 0.6 + wobble * 0.35
        for i in range(steps):
            ang = 2 * math.pi * i / steps
            r = radius
            for k, amp, phase_speed in harmonics:
                r += amp * radius * wobble * math.sin(k * ang + t * phase_speed * speed)
            x = r * math.cos(ang)
            y = r * math.sin(ang)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.translate(self.width() // 2, self.height() // 2)

        t = time.monotonic() - self.t0

        for rad, alpha in self.ripples:
            ring = QColor(self.color)
            ring.setAlpha(int(alpha * (0.4 if self.dimmed else 1.0)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ring, 2))
            painter.drawEllipse(QRectF(-rad, -rad, rad * 2, rad * 2))
            painter.setPen(Qt.PenStyle.NoPen)

        glow = QColor(self.color)
        glow.setAlpha(8 if self.dimmed else 26)
        painter.setBrush(QBrush(glow))
        painter.drawPath(self._blob_path(self.radius * 1.75, t, self.wobble * 0.6))

        glow2 = QColor(self.color)
        glow2.setAlpha(18 if self.dimmed else 55)
        painter.setBrush(QBrush(glow2))
        painter.drawPath(self._blob_path(self.radius * 1.35, t, self.wobble * 0.8))

        core = QColor(self.color)
        core.setAlpha(90 if self.dimmed else 255)
        painter.setBrush(QBrush(core))
        painter.drawPath(self._blob_path(self.radius, t, self.wobble))

        highlight = QColor(255, 255, 255)
        highlight.setAlpha(30 if self.dimmed else 75)
        painter.setBrush(QBrush(highlight))
        r = self.radius * 0.22
        painter.drawEllipse(int(-self.radius * 0.55), int(-self.radius * 0.8), int(r * 2), int(r * 2))

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
    orb.setGeometry(0, 0, 110, 110)
    app.processEvents()
    orb.move(0, 0)
    orb.setGeometry(0, 0, 110, 110)
    os.system('niri msg action move-floating-window -x 0 -y 0 >/dev/null 2>&1 &')
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
