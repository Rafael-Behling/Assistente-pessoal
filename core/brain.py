import json
import time
import threading
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))

from core.llm.ollama import OllamaProvider
from core.tts import TTS
from core.listener import Listener
from core.stt import STT
from core.memory import Memory
from core.commands import Commands

class Brain:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.json"
        self.config_path = config_path
        self.load_config()
        self.listener = Listener()
        stt_cfg = self.config.get('stt', {})
        self.stt = STT(model_size=stt_cfg.get('model', 'base'))
        if stt_cfg.get('preload', True):
            threading.Thread(target=self.stt.load_model, daemon=True).start()
        self.tts = TTS(config_path)
        self.memory = Memory(self.config.get('memory', {}))
        self.llm = self.init_llm()
        self.commands = Commands()
        self.last_transcript = None
        self.last_stt_s = None
        self.last_llm_s = None
        self.last_command = None
    
    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except:
            self.config = {}
    
    def init_llm(self):
        llm_config = self.config.get('llm', {})
        mode = llm_config.get('mode', 'local')
        if mode == 'local':
            local_cfg = llm_config.get('local', {})
            return OllamaProvider(local_cfg)
        # API por enquanto não implementado, usa local como fallback
        local_cfg = llm_config.get('local', {})
        return OllamaProvider(local_cfg)
    
    def start_listening(self):
        self.listener.start_recording()
    
    def transcribe_audio(self, audio_path):
        print("[BRAIN] Transcrevendo...")
        start = time.perf_counter()
        text = self.stt.transcribe(audio_path)
        self.last_stt_s = time.perf_counter() - start
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
    
    def think(self, query):
        self.last_command = None
        start = time.perf_counter()
        command = self.commands.run(query)
        if command is not None:
            self.last_llm_s = time.perf_counter() - start
            self.last_command = command.name
            print(f"[BRAIN] Comando: {command.name} -> {command.response}")
            return command.response

        print("[BRAIN] Pensando...")
        llm_cfg = self.config.get('llm', {})
        system_prompt = llm_cfg.get('system_prompt', 'Você é a Sexta-Feira, um assistente pessoal conciso, prático e direto em português.')
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        start = time.perf_counter()
        response = self.llm.chat(messages)
        self.last_llm_s = time.perf_counter() - start
        if not response:
            response = "Não consegui processar sua solicitação."
        
        print(f"[BRAIN] Resposta: {response}")
        return response

    def log_turn(self, transcript, response):
        model = self.config.get('llm', {}).get('local', {}).get('model')
        self.memory.log_turn(
            transcript,
            response,
            stt_s=self.last_stt_s,
            llm_s=self.last_llm_s,
            model=model,
            command=self.last_command,
        )
    
    def speak(self, text):
        self.tts.speak(text)
