import sys
import json
import fcntl
import subprocess
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from core.log import setup_log
from ui.menu import VoiceMenu
from PyQt6.QtWidgets import QApplication

LOCK_PATH = "/tmp/sexta-feira.lock"
MAX_RESTARTS = 3


def acquire_single_instance():
    lock_file = open(LOCK_PATH, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Sexta-Feira já está rodando. Feche a instância atual antes de abrir outra.")
        return None
    return lock_file


def run_orb():
    restarts = 0
    while True:
        orb_proc = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).parent / "ui" / "orb.py")],
            cwd=str(Path(__file__).parent),
        )
        try:
            orb_proc.wait()
        except KeyboardInterrupt:
            if orb_proc.poll() is None:
                orb_proc.terminate()
            return
        code = orb_proc.returncode
        if code == 0 or restarts >= MAX_RESTARTS:
            return
        restarts += 1
        print(f"[MAIN] Orb saiu com código {code}. Reiniciando ({restarts}/{MAX_RESTARTS})...")
        time.sleep(2)


def main():
    setup_log(Path(__file__).parent / "data" / "sexta-feira.log")
    lock = acquire_single_instance()
    if lock is None:
        return

    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if config.get('voice'):
            run_orb()
            return
    except Exception as e:
        print(f"Erro ao iniciar: {e}")

    app = QApplication(sys.argv)
    menu = VoiceMenu()
    menu.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
