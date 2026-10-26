import queue
import tempfile
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd
from scipy.io import wavfile


class VADListener:
    def __init__(self, config, on_utterance, sample_rate=16000, block_ms=30):
        cfg = config.get('vad', {})
        self.sample_rate = sample_rate
        self.block_ms = block_ms
        self.block_size = int(sample_rate * block_ms / 1000)
        self.on_utterance = on_utterance

        self.energy_threshold = cfg.get('energy_threshold', 0.01)
        self.noise_multiplier = cfg.get('noise_multiplier', 2.5)
        self.min_speech_ms = cfg.get('min_speech_ms', 300)
        self.end_silence_ms = cfg.get('end_silence_ms', 800)
        self.pre_roll_ms = cfg.get('pre_roll_ms', 300)
        self.max_utterance_s = cfg.get('max_utterance_s', 15)
        self.calibration_ms = cfg.get('calibration_ms', 1000)
        self.start_frames = cfg.get('start_frames', 5)
        self.device = cfg.get('device', None)
        self.debug = cfg.get('debug', False)
        self.engine = cfg.get('engine', 'energy')
        self.prob_threshold = cfg.get('prob_threshold', 0.5)
        self._silero = None
        self._torch = None
        if self.engine == 'silero':
            try:
                from silero_vad import load_silero_vad
                import torch
                self._silero = load_silero_vad()
                self._torch = torch
                print("[VAD] Motor Silero ativado")
            except Exception as e:
                print(f"[VAD] Silero indisponível ({e}); usando motor de energia")
                self.engine = 'energy'

        self.pre_roll_frames = max(1, int(self.pre_roll_ms / block_ms))
        self.max_frames = int(self.max_utterance_s * 1000 / block_ms)

        self.queue = queue.Queue()
        self.running = False
        self.paused = False
        self.stream = None
        self.thread = None
        self.noise_floor = None
        self.current_rms = 0.0

    def _callback(self, indata, frames, time_info, status):
        if self.paused or not self.running:
            return
        frame = indata[:, 0]
        self.current_rms = float(np.sqrt(np.mean(frame ** 2)))
        self.queue.put(frame.copy())

    def _drain(self):
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def _save(self, audio):
        temp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        path = temp.name
        temp.close()
        data = np.clip(audio, -1.0, 1.0)
        wavfile.write(path, self.sample_rate, (data * 32767).astype(np.int16))
        return path

    def _process(self, audio):
        path = self._save(audio)
        self.paused = True
        try:
            self.on_utterance(path)
        except Exception as e:
            print(f"[VAD] Erro ao processar fala: {e}")
        finally:
            time.sleep(0.4)
            self._drain()
            self.paused = False

    def _loop(self):
        pre_roll = deque(maxlen=self.pre_roll_frames)
        utterance = []
        speaking = False
        silence_ms = 0
        voiced_ms = 0
        above_count = 0
        calib = []
        calib_frames = max(1, int(self.calibration_ms / self.block_ms))
        last_debug = 0.0

        while self.running:
            try:
                frame = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if self.paused:
                continue

            if self.engine == 'silero' and self._silero is not None:
                prob = float(self._silero(self._torch.from_numpy(frame), self.sample_rate).item())
                level = prob
                threshold = self.prob_threshold
                above = prob > self.prob_threshold
            else:
                rms = float(np.sqrt(np.mean(frame ** 2)))

                if self.noise_floor is None:
                    calib.append(rms)
                    if len(calib) >= calib_frames:
                        self.noise_floor = float(np.percentile(calib, 20))
                        threshold = max(self.energy_threshold, self.noise_floor * self.noise_multiplier)
                        print(f"[VAD] Calibrado: ruído={self.noise_floor:.4f} limiar={threshold:.4f}")
                    continue

                threshold = max(self.energy_threshold, self.noise_floor * self.noise_multiplier)

                if not speaking and rms < threshold * 0.8:
                    self.noise_floor = 0.98 * self.noise_floor + 0.02 * rms
                    threshold = max(self.energy_threshold, self.noise_floor * self.noise_multiplier)

                level = rms
                above = rms > threshold

            if self.debug and time.time() - last_debug > 1.0:
                print(f"[VAD] nível={level:.4f} limiar={threshold:.4f} speaking={speaking}")
                last_debug = time.time()

            if not speaking:
                pre_roll.append(frame)
                if above:
                    above_count += 1
                    if above_count >= self.start_frames:
                        speaking = True
                        utterance = list(pre_roll)
                        voiced_ms = above_count * self.block_ms
                        silence_ms = 0
                        print("[VAD] Fala detectada")
                else:
                    above_count = 0
            else:
                utterance.append(frame)
                if above:
                    voiced_ms += self.block_ms
                    silence_ms = 0
                else:
                    silence_ms += self.block_ms

                done = silence_ms >= self.end_silence_ms or len(utterance) >= self.max_frames
                if done:
                    if voiced_ms >= self.min_speech_ms and utterance:
                        audio = np.concatenate(utterance)
                        print(f"[VAD] Fim da fala ({len(audio) / self.sample_rate:.1f}s)")
                        self._process(audio)
                    speaking = False
                    utterance = []
                    silence_ms = 0
                    voiced_ms = 0
                    above_count = 0
                    pre_roll.clear()

    def start(self):
        if self.running:
            return
        self.running = True
        self.pre_roll_frames = max(1, int(self.pre_roll_ms / self.block_ms))
        self.stream = sd.InputStream(
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            device=self.device,
            dtype='float32',
            callback=self._callback,
        )
        self.stream.start()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
