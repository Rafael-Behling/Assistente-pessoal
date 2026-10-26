import sys
import json
import os
import fcntl
import subprocess
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from ui.menu import VoiceMenu
from PyQt6.QtWidgets import QApplication

LOCK_PATH = "/tmp/sexta-feira.lock"


def acquire_single_instance():
    lock_file = open(LOCK_PATH, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Sexta-Feira já está rodando. Feche a instância atual antes de abrir outra.")
        return None
    return lock_file


def main():
    lock = acquire_single_instance()
    if lock is None:
        return

    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if config.get('voice'):
            env = os.environ.copy()
            env['QT_QPA_PLATFORM'] = 'xcb'
            env['PYTHONPATH'] = str(Path(__file__).parent)

            orb_proc = subprocess.Popen(
                [sys.executable, "-u", str(Path(__file__).parent / "ui" / "orb.py")],
                env=env,
                cwd=str(Path(__file__).parent),
            )

            try:
                orb_proc.wait()
            except KeyboardInterrupt:
                pass
            finally:
                if orb_proc.poll() is None:
                    try:
                        orb_proc.terminate()
                    except Exception:
                        pass
            return
    except Exception as e:
        print(f"Erro ao iniciar: {e}")

    app = QApplication(sys.argv)
    menu = VoiceMenu()
    menu.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
