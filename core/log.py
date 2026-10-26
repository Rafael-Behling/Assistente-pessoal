import sys


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
            except Exception:
                pass

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass


def setup_log(path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        f = open(path, 'a', buffering=1, encoding='utf-8')
        sys.stdout = _Tee(sys.stdout, f)
        sys.stderr = _Tee(sys.stderr, f)
        print(f"[LOG] Registrando em {path}")
    except Exception as e:
        print(f"[LOG] Falha ao abrir log: {e}")
