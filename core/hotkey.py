import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import json
import time
import selectors
import evdev
from evdev import ecodes

from core.ipc import IPC, SOCKET_PATH


class HotkeyListener:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = BASE_DIR / "config.json"
        self.config_path = config_path
        self.load_config()
        self.ipc = IPC()
        self.pressed = False
        self.devices = {}
        self.selector = selectors.DefaultSelector()
        self.key_code = self.resolve_key(self.get_hotkey())

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception:
            self.config = {"activation": {"hotkey": "f8", "mode": "push_to_talk"}}

    def get_hotkey(self):
        return self.config.get('activation', {}).get('hotkey', 'f8').lower()

    def resolve_key(self, name):
        name = name.upper()
        if not name.startswith("KEY_"):
            name = f"KEY_{name}"
        code = getattr(ecodes, name, None)
        if code is None:
            print(f"[HOTKEY] Tecla '{name}' desconhecida, usando KEY_F8")
            code = ecodes.KEY_F8
        return code

    def key_name(self):
        return ecodes.KEY[self.key_code]

    def find_keyboards(self):
        keyboards = []
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except PermissionError:
                continue
            except Exception:
                continue
            caps = dev.capabilities()
            keys = caps.get(ecodes.EV_KEY, [])
            if ecodes.KEY_A in keys and ecodes.KEY_F8 in keys:
                keyboards.append(dev)
            else:
                dev.close()
        return keyboards

    def add_device(self, dev):
        if dev.path in self.devices:
            return
        self.devices[dev.path] = dev
        self.selector.register(dev, selectors.EVENT_READ)
        print(f"[HOTKEY] Ouvindo teclado: {dev.name} ({dev.path})")

    def remove_device(self, dev):
        try:
            self.selector.unregister(dev)
        except Exception:
            pass
        self.devices.pop(dev.path, None)
        try:
            dev.close()
        except Exception:
            pass

    def rescan(self):
        for dev in self.find_keyboards():
            self.add_device(dev)

    def handle_event(self, event):
        if event.type != ecodes.EV_KEY or event.code != self.key_code:
            return
        if event.value == 1 and not self.pressed:
            self.pressed = True
            print(f"[HOTKEY] {self.key_name()} pressionado - gravando")
            self.ipc.send({"type": "START_LISTEN"})
        elif event.value == 0 and self.pressed:
            self.pressed = False
            print(f"[HOTKEY] {self.key_name()} solto - processando")
            self.ipc.send({"type": "STOP_LISTEN"})

    def wait_for_socket(self):
        for _ in range(40):
            if Path(SOCKET_PATH).exists():
                return True
            time.sleep(0.25)
        return False

    def connect(self):
        try:
            self.ipc.connect_client()
            return True
        except Exception:
            return False

    def start(self):
        if not self.wait_for_socket():
            print("[HOTKEY] Socket do orb não encontrado. A bolinha está rodando?")
            return
        if not self.connect():
            print("[HOTKEY] Não consegui conectar ao orb.")
            return

        try:
            self.rescan()
        except PermissionError:
            print("[HOTKEY] Sem permissão para ler /dev/input.")
            print("[HOTKEY] Aplique a regra udev (66-sexta-feira-input.rules) ou entre no grupo 'input'.")
            return

        if not self.devices:
            print("[HOTKEY] Nenhum teclado acessível encontrado em /dev/input.")
            return

        print(f"[HOTKEY] Atalho: {self.key_name()}")
        print("[HOTKEY] Segure para falar, solte para processar")

        while True:
            for key, _ in self.selector.select(timeout=2.0):
                dev = key.fileobj
                try:
                    for event in dev.read():
                        self.handle_event(event)
                except OSError:
                    print(f"[HOTKEY] Teclado desconectado: {dev.path}")
                    self.remove_device(dev)
                    self.rescan()


if __name__ == '__main__':
    HotkeyListener().start()
