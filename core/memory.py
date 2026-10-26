import json
from datetime import datetime
from pathlib import Path


class Memory:
    def __init__(self, config=None):
        config = config or {}
        self.enabled = config.get('save_transcripts', True)
        base_dir = Path(config.get('dir', 'data'))
        if not base_dir.is_absolute():
            base_dir = Path(__file__).parent.parent / base_dir
        self.dir = base_dir / "conversas"

    def log_turn(self, transcript, response, stt_s=None, llm_s=None, model=None, command=None):
        if not self.enabled:
            return
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            entry = {
                "ts": now.isoformat(timespec='seconds'),
                "voce": transcript,
                "sexta": response,
                "stt_s": round(stt_s, 2) if stt_s is not None else None,
                "llm_s": round(llm_s, 2) if llm_s is not None else None,
                "model": model,
            }
            if command:
                entry["command"] = command
            path = self.dir / f"{now:%Y-%m-%d}.jsonl"
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[MEMORY] Falha ao salvar histórico: {e}")
