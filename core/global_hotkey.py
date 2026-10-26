import selectors
import threading

import evdev
from evdev import ecodes


class GlobalHotkey:
    def __init__(self, callback, name="Ctrl+E"):
        self.callback = callback
        self.name = name
        self.selector = selectors.DefaultSelector()
        self.devices = {}
        self.running = False
        self.thread = None
        self.ctrl = False
        self.fired = False

    def _find_keyboards(self):
        keyboards = []
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except Exception:
                continue
            caps = dev.capabilities().get(ecodes.EV_KEY, [])
            if ecodes.KEY_A in caps and ecodes.KEY_E in caps and (
                ecodes.KEY_LEFTCTRL in caps or ecodes.KEY_RIGHTCTRL in caps
            ):
                keyboards.append(dev)
            else:
                dev.close()
        return keyboards

    def _add(self, dev):
        if dev.path in self.devices:
            return
        self.devices[dev.path] = dev
        self.selector.register(dev, selectors.EVENT_READ)
        print(f"[HOTKEY] Ouvindo {dev.name} ({dev.path}) - {self.name} fecha")

    def _remove(self, dev):
        try:
            self.selector.unregister(dev)
        except Exception:
            pass
        self.devices.pop(dev.path, None)
        try:
            dev.close()
        except Exception:
            pass
        self.ctrl = False
        self.fired = False

    def _rescan(self):
        for dev in self._find_keyboards():
            self._add(dev)

    def _handle(self, event):
        if event.type != ecodes.EV_KEY:
            return
        if event.code in (ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL):
            self.ctrl = event.value in (1, 2)
            return
        if event.code != ecodes.KEY_E:
            return
        if event.value == 1 and self.ctrl and not self.fired:
            self.fired = True
            print(f"[HOTKEY] {self.name} - fechando")
            try:
                self.callback()
            except Exception as e:
                print(f"[HOTKEY] Erro no atalho: {e}")
        elif event.value == 0:
            self.fired = False

    def _run(self):
        try:
            self._rescan()
        except PermissionError:
            print("[HOTKEY] Sem permissão para ler /dev/input.")
            print("[HOTKEY] Aplique a regra udev 66-sexta-feira-input.rules.")
            return
        except Exception as e:
            print(f"[HOTKEY] Erro ao buscar teclado: {e}")
            return

        if not self.devices:
            print("[HOTKEY] Nenhum teclado acessível encontrado.")
            return

        while self.running:
            try:
                events = self.selector.select(timeout=0.5)
            except Exception:
                if not self.running:
                    break
                continue
            for key, _ in events:
                dev = key.fileobj
                try:
                    for event in dev.read():
                        self._handle(event)
                except OSError:
                    if not self.running:
                        break
                    print(f"[HOTKEY] Teclado desconectado: {dev.path}")
                    self._remove(dev)
                    try:
                        self._rescan()
                    except Exception:
                        pass

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        for dev in list(self.devices.values()):
            try:
                dev.close()
            except Exception:
                pass
        self.devices.clear()
