import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os

class Listener:
    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = []
        self.stream = None
        self.is_recording = False
    
    def start_recording(self):
        self.recording = []
        self.is_recording = True
        
        def callback(indata, frames, time, status):
            if status:
                print(f"Status: {status}")
            if self.is_recording:
                self.recording.append(indata.copy())
        
        self.stream = sd.InputStream(
            channels=self.channels,
            samplerate=self.sample_rate,
            callback=callback
        )
        self.stream.start()
        print("[LISTENER] Gravando...")
    
    def stop_recording(self):
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        print("[LISTENER] Gravação parada")
        
        if not self.recording:
            return None
        
        audio = np.concatenate(self.recording, axis=0)
        # Salvar temporário
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_path = temp_file.name
        temp_file.close()
        wav.write(temp_path, self.sample_rate, (audio * 32767).astype(np.int16))
        return temp_path
