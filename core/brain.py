import difflib
import json
import re
import time
import threading
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))

import os
from datetime import datetime

from core.llm.ollama import OllamaProvider
from core.llm.openrouter import OpenRouterProvider
from core.tts import TTS
from core.listener import Listener
from core.stt import STT
from core.memory import Memory
from core.commands import Commands, normalize, format_date
from core.websearch import looks_like_knowledge_question, search_context

class Brain:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.json"
        self.config_path = config_path
        self.load_config()
        act_cfg = self.config.get('activation', {})
        self.wake_enabled = act_cfg.get('mode', 'always_on') == 'wake_word'
        self.wake_words = [self._norm_wake(w) for w in act_cfg.get('wake_words', ['sexta feira'])]
        self.wake_prompt = ', '.join(w.title() for w in self.wake_words[:1]) + '.'
        self.session_timeout_s = float(act_cfg.get('session_timeout_s', 20))
        self.session_open_until = 0.0
        self.history = []
        self.listener = Listener()
        stt_cfg = self.config.get('stt', {})
        self.stt = STT(
            model_size=stt_cfg.get('model', 'base'),
            language=stt_cfg.get('language', 'pt'),
            beam_size=stt_cfg.get('beam_size', 1),
        )
        self.stt_wake = None
        if self.wake_enabled and stt_cfg.get('wake_model', 'tiny'):
            self.stt_wake = STT(
                model_size=stt_cfg.get('wake_model', 'tiny'),
                language=stt_cfg.get('language', 'pt'),
                beam_size=1,
            )
            if stt_cfg.get('preload', True):
                threading.Thread(target=self.stt_wake.load_model, daemon=True).start()
        if stt_cfg.get('preload', True):
            threading.Thread(target=self.stt.load_model, daemon=True).start()
        self.tts = TTS(config_path)
        self.memory = Memory(self.config.get('memory', {}))
        self.llm = self.init_llm()
        self.commands = Commands(memory=self.memory, config=self.config)
        self._cancelled = False
        self._barge_active = False
        self.warmup = self.config.get('llm', {}).get('warmup', True)
        if self.warmup and type(self.llm).__name__ == 'OllamaProvider':
            threading.Thread(target=self._warmup_llm, daemon=True).start()
        if self.config.get('reminders', {}).get('enabled', True):
            threading.Thread(target=self._reminder_loop, daemon=True).start()
        self.last_transcript = None
        self.last_stt_s = None
        self.last_llm_s = None
        self.last_command_s = None
        self.last_command = None
        self.last_model = None

    def _warmup_llm(self):
        try:
            self.llm.chat([{'role': 'user', 'content': 'oi'}])
            print("[BRAIN] LLM aquecido")
        except Exception:
            pass

    def _reminder_loop(self):
        from core.tts import TTS
        from datetime import datetime
        import subprocess
        while True:
            time.sleep(20)
            try:
                due = self.memory.due_reminders(datetime.now().isoformat(timespec='seconds'))
                for r in due:
                    print(f"[BRAIN] Lembrete: {r['text']}")
                    try:
                        subprocess.Popen(['notify-send', '-a', 'Sexta-Feira', 'Sexta-Feira - Lembrete', r['text']])
                    except Exception:
                        pass
                    self.speak(f'Lembrete: {r["text"]}')
            except Exception as e:
                print(f"[BRAIN] Erro no loop de lembretes: {e}")
    
    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"[BRAIN] Falha ao carregar config: {e}")
            self.config = {}
    
    def init_llm(self):
        llm_config = self.config.get('llm', {})
        mode = llm_config.get('mode', 'local')
        if mode == 'api':
            api_cfg = llm_config.get('api', {})
            if api_cfg.get('api_key') or os.environ.get('OPENROUTER_API_KEY'):
                return OpenRouterProvider(api_cfg)
            print("[BRAIN] llm.mode=api sem api_key (config.json ou OPENROUTER_API_KEY). Usando local.")
        return OllamaProvider(llm_config.get('local', {}))
    
    def _norm_wake(self, text):
        text = normalize(text)
        text = text.replace('-', ' ')
        return re.sub(r'\s+', ' ', text).strip()

    def _find_wake(self, n):
        for word in self.wake_words:
            if word and word in n:
                return word
        words = n.split()
        for word in self.wake_words:
            target = word.split()
            wlen = len(target)
            if not wlen or len(words) < wlen:
                continue
            for i in range(len(words) - wlen + 1):
                window = ' '.join(words[i:i + wlen])
                if difflib.SequenceMatcher(None, window, word).ratio() >= 0.8:
                    return ' '.join(words[i:i + wlen])
        return None

    def check_wake(self, text):
        if not self.wake_enabled:
            return True, text, False
        n = self._norm_wake(text)
        wake = self._find_wake(n)
        if wake:
            if time.monotonic() >= self.session_open_until:
                self.history = []
            n = re.sub(r'\s+', ' ', n.replace(wake, ' ', 1)).strip(' ,.!?;:')
            self.session_open_until = time.monotonic() + self.session_timeout_s
            return True, n, not n
        if time.monotonic() < self.session_open_until:
            self.session_open_until = time.monotonic() + self.session_timeout_s
            return True, n, False
        return False, '', False

    def session_open(self):
        return not self.wake_enabled or time.monotonic() < self.session_open_until

    def _push_history(self, user, assistant):
        self.history.append({'role': 'user', 'content': user})
        self.history.append({'role': 'assistant', 'content': assistant})
        if len(self.history) > 10:
            self.history = self.history[-10:]

    def handle_utterance(self, audio_path, on_sentence=None):
        self._cancelled = False
        self._barge_active = False
        self.last_stt_s = 0
        if self.stt_wake is not None:
            fast_text = self.transcribe_audio(audio_path, stt=self.stt_wake, initial_prompt=self.wake_prompt, delete=False)
            if not fast_text:
                self._delete_audio(audio_path)
                return None
            matched, _, _ = self.check_wake(fast_text)
            if not matched:
                print("[BRAIN] Sem palavra de ativação, ignorando")
                self._delete_audio(audio_path)
                return None
            text = self.transcribe_audio(audio_path)
            if not text:
                return None
            matched, query, needs_attention = self.check_wake(text)
            if not matched:
                self.session_open_until = time.monotonic() + self.session_timeout_s
                matched, query, needs_attention = True, self._norm_wake(text), False
        else:
            text = self.transcribe_audio(audio_path)
            if not text:
                return None
            matched, query, needs_attention = self.check_wake(text)
            if not matched:
                print("[BRAIN] Sem palavra de ativação, ignorando")
                return None
        if needs_attention:
            response = 'Sim?'
            if on_sentence:
                on_sentence(response)
            return (text, '', response)
        response = self.think(query, on_sentence)
        return (text, query, response)

    def _delete_audio(self, audio_path):
        try:
            os.unlink(audio_path)
        except Exception:
            pass

    def cancel_speech(self):
        print("[BRAIN] Interrompido")
        self._cancelled = True
        self.tts.stop()

    def wake_transcribe(self, audio_path):
        if self.stt_wake is None:
            return ''
        return self.stt_wake.transcribe(audio_path, initial_prompt=self.wake_prompt)

    def is_wake(self, text):
        if not text:
            return False
        return self._find_wake(self._norm_wake(text)) is not None

    @property
    def barge_enabled(self):
        return bool(self.stt_wake) and self.config.get('activation', {}).get('barge_in', True)

    def start_listening(self):
        self.listener.start_recording()
    
    def transcribe_audio(self, audio_path, stt=None, initial_prompt=None, delete=True):
        stt = stt or self.stt
        print("[BRAIN] Transcrevendo...")
        start = time.perf_counter()
        text = stt.transcribe(audio_path, initial_prompt=initial_prompt, delete=delete)
        self.last_stt_s = (self.last_stt_s or 0) + time.perf_counter() - start
        if not text:
            print("[BRAIN] Nenhum texto transcrito")
            return None

        self.last_transcript = text
        print(f"[BRAIN] Você disse: {text}")
        return text

    def stop_and_transcribe(self):
        audio_path = self.listener.stop_recording()
        if not audio_path:
            print("[BRAIN] Nenhum áudio gravado")
            return None
        return self.transcribe_audio(audio_path)
    
    def think(self, query, on_sentence=None):
        self._cancelled = False
        self.last_command = None
        self.last_command_s = None
        self.last_llm_s = None
        self.last_model = None
        start = time.perf_counter()
        command = self.commands.run(query)
        if command is not None:
            self.last_command_s = time.perf_counter() - start
            self.last_command = command.name
            self._push_history(query, command.response)
            print(f"[BRAIN] Comando: {command.name} -> {command.response}")
            return command.response
        self.last_command_s = time.perf_counter() - start

        print("[BRAIN] Pensando...")
        llm_cfg = self.config.get('llm', {})
        system_prompt = llm_cfg.get('system_prompt', 'Você é a Sexta-Feira, um assistente pessoal conciso, prático e direto em português.')
        facts = self.memory.load_facts()
        if facts:
            system_prompt += '\n\nInformações que você sabe sobre o usuário:\n- ' + '\n- '.join(facts)
        now = datetime.now()
        system_prompt = (
            f"{system_prompt}\n\n"
            f"Data e hora atuais: {format_date(now)} {now:%H:%M}. "
            "Use essa informação para perguntas sobre data, hora ou eventos recentes."
        )
        system_prompt += (
            "\n\nSua resposta será lida em voz alta. Não use markdown, listas, títulos ou símbolos. "
            "Escreva números por extenso quando fizer sentido para a fala. "
            "Nunca diga o seu próprio nome na resposta."
        )
        if self.config.get('web_search', {}).get('enabled', True) and looks_like_knowledge_question(normalize(query)):
            context = search_context(query)
            if context:
                print("[BRAIN] Usando contexto da web")
                system_prompt += f"\n\nInformações da web (use como fonte atualizada):\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            *self.history,
            {"role": "user", "content": query}
        ]

        start_llm = time.perf_counter()
        full = ''
        if on_sentence is not None and hasattr(self.llm, 'chat_stream'):
            parts = []
            pending = ''
            for chunk in self.llm.chat_stream(messages):
                if self._cancelled or self._barge_active:
                    print("[BRAIN] Stream cancelado")
                    break
                pending += chunk
                while True:
                    m = re.search(r'[.!?](?:\s|$)', pending)
                    if not m:
                        break
                    sentence = pending[:m.end()].strip()
                    pending = pending[m.end():]
                    if sentence:
                        parts.append(sentence)
                        on_sentence(sentence)
                        if self._cancelled or self._barge_active:
                            break
                if self._cancelled or self._barge_active:
                    break
            if pending.strip() and not (self._cancelled or self._barge_active):
                parts.append(pending.strip())
                on_sentence(pending.strip())
            full = ' '.join(parts).strip()
        else:
            full = self.llm.chat(messages)
            if not full:
                full = "Não consegui processar sua solicitação."
            if on_sentence is not None and not (self._cancelled or self._barge_active):
                on_sentence(full)
        self.last_llm_s = time.perf_counter() - start_llm
        self.last_model = self.llm.model
        self._push_history(query, full)

        print(f"[BRAIN] Resposta: {full}")
        return full

    def log_turn(self, transcript, response):
        self.memory.log_turn(
            transcript,
            response,
            stt_s=self.last_stt_s,
            llm_s=self.last_llm_s,
            command_s=self.last_command_s,
            model=self.last_model,
            command=self.last_command,
        )
    
    def speak(self, text):
        if self._cancelled or self._barge_active:
            return
        self.tts.speak(text)
