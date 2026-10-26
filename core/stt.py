from faster_whisper import WhisperModel
import os
import threading

import numpy as np
from scipy.io import wavfile


class STT:
    def __init__(self, model_size="base", device="cpu", compute_type="int8", language="pt", beam_size=1):
        self.model = None
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self._lock = threading.Lock()

    def load_model(self):
        with self._lock:
            if self.model is None:
                print(f"[STT] Carregando modelo Whisper {self.model_size}...")
                self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
                print("[STT] Modelo carregado")

    def _read_audio(self, audio_path):
        sample_rate, data = wavfile.read(audio_path)
        if data.dtype == np.int16:
            audio = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            audio = data.astype(np.float32) / 2147483648.0
        else:
            audio = data.astype(np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        target_rate = 16000
        if sample_rate != target_rate:
            from scipy.signal import resample_poly
            audio = resample_poly(audio, target_rate, sample_rate).astype(np.float32)
        audio = self._trim_silence(audio, target_rate)
        audio = self._normalize(audio)
        return audio, target_rate

    def _trim_silence(self, audio, sample_rate, threshold=0.0015):
        frame = int(sample_rate * 0.02)
        if len(audio) < frame * 2:
            return audio
        total = (len(audio) // frame) * frame
        frames = audio[:total].reshape(-1, frame)
        rms = np.sqrt(np.mean(frames ** 2, axis=1))
        voiced = np.where(rms > threshold)[0]
        if len(voiced) == 0:
            return audio
        start = max(0, (voiced[0] - 3)) * frame
        end = min(len(audio), (voiced[-1] + 4) * frame)
        return audio[start:end]

    def _normalize(self, audio):
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak <= 0:
            return audio
        gain = min(4.0, 0.9 / peak)
        return (audio * gain).astype(np.float32)

    def transcribe(self, audio_path, language=None, initial_prompt=None, delete=True):
        if not os.path.exists(audio_path):
            return ""
        self.load_model()
        try:
            audio, sample_rate = self._read_audio(audio_path)
            segments, info = self.model.transcribe(
                audio,
                language=language or self.language,
                beam_size=self.beam_size,
                vad_filter=False,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
                temperature=0.0,
                initial_prompt=initial_prompt or None,
            )
            text = " ".join([segment.text for segment in segments])
            return text.strip()
        except Exception as e:
            print(f"[STT] Erro: {e}")
            return ""
        finally:
            if delete:
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass
