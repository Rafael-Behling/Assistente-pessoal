import json
import os
import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    import edge_tts
except ImportError:
    edge_tts = None

class TTS:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.json"
        self.config_path = config_path
        self.load_config()
    
    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except:
            self.config = {"voice": None, "volume": 1.0, "rate": 1.0}
    
    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as fjson:
            json.dump(self.config, fjson, indent=2, ensure_ascii=False)
    
    def get_voice(self):
        return self.config.get("voice")
    
    def _play_audio(self, path):
        players = {
            'mpv': ['--no-video', '--quiet'],
            'ffplay': ['-nodisp', '-autoexit', '-loglevel', 'quiet'],
        }
        for player, args in players.items():
            exe = shutil.which(player)
            if not exe:
                continue
            try:
                result = subprocess.run([exe, *args, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if result.returncode == 0:
                    return
            except Exception:
                continue
        print("[TTS] Nenhum player de áudio encontrado")

    async def speak_async(self, text, voice=None):
        if not edge_tts:
            print("edge-tts não instalado")
            return
        voice = voice or self.get_voice()
        if not voice:
            print("Nenhuma voz selecionada")
            return
        temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        path = temp.name
        temp.close()
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(path)
            await asyncio.to_thread(self._play_audio, path)
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass
    
    def speak(self, text, voice=None):
        asyncio.run(self.speak_async(text, voice))
    
    @staticmethod
    async def _list_voices_async():
        if not edge_tts:
            return []
        voices = await edge_tts.list_voices()
        voices.sort(key=lambda x: (x['Locale'], x['ShortName']))
        return voices
    
    @staticmethod
    def list_voices():
        if not edge_tts:
            return []
        try:
            return asyncio.run(TTS._list_voices_async())
        except Exception:
            try:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(TTS._list_voices_async())
            except Exception:
                return []
