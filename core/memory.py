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
        self.facts_path = base_dir / "fatos.json"
        self.reminders_path = base_dir / "lembretes.json"

    def load_facts(self):
        try:
            with open(self.facts_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def remember_fact(self, fact):
        try:
            facts = self.load_facts()
            fact = fact.strip()
            if fact and fact not in facts:
                facts.append(fact)
                self.facts_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.facts_path, 'w', encoding='utf-8') as f:
                    json.dump(facts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[MEMORY] Falha ao salvar fato: {e}")

    def clear_facts(self):
        try:
            self.facts_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.facts_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False)
        except Exception as e:
            print(f"[MEMORY] Falha ao limpar fatos: {e}")

    def _read_reminders(self):
        try:
            with open(self.reminders_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _write_reminders(self, items):
        try:
            self.reminders_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.reminders_path, 'w', encoding='utf-8') as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[MEMORY] Falha ao salvar lembretes: {e}")

    def add_reminder(self, when_iso, text):
        items = self._read_reminders()
        items.append({"when": when_iso, "text": text})
        items.sort(key=lambda r: r["when"])
        self._write_reminders(items)

    def due_reminders(self, now_iso):
        items = self._read_reminders()
        due = [r for r in items if r["when"] <= now_iso]
        if due:
            self._write_reminders([r for r in items if r["when"] > now_iso])
        return due

    def count_reminders(self):
        return len(self._read_reminders())

    def log_turn(self, transcript, response, stt_s=None, llm_s=None, command_s=None, model=None, command=None):
        if not self.enabled:
            return
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            entry = {
                "ts": now.isoformat(timespec='seconds'),
                "voce": transcript,
                "sexta": response,
            }
            if command:
                entry["command"] = command
            if command_s is not None:
                entry["command_s"] = round(command_s, 2)
            if llm_s is not None:
                entry["llm_s"] = round(llm_s, 2)
            if model:
                entry["model"] = model
            path = self.dir / f"{now:%Y-%m-%d}.jsonl"
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[MEMORY] Falha ao salvar histórico: {e}")
