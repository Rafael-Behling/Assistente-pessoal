import json
import sys
import time
import threading
from pathlib import Path

import numpy as np

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vad import VADListener


def test_callback_gate():
    vad = VADListener({}, lambda p: None)
    vad.running = True
    vad.paused = True
    indata = np.zeros((480, 1), dtype='float32')

    vad._callback(indata, 480, None, None)
    assert vad.queue.qsize() == 0

    vad.monitoring = True
    vad._callback(indata, 480, None, None)
    assert vad.queue.qsize() == 1

    vad.paused = False
    vad._callback(indata, 480, None, None)
    assert vad.queue.qsize() == 2


def test_barge_watch_triggers():
    class FakeBarge:
        def wake_transcribe(self, path):
            return 'sexta feira oi'

        def is_wake(self, text):
            return 'sexta feira' in (text or '')

    fired = []
    vad = VADListener({}, lambda p: None, barge=FakeBarge(), on_barge_in=lambda: fired.append(1), block_ms=30)
    vad.running = True
    vad.monitoring = True
    frame = np.zeros(480, dtype='float32')

    def feeder():
        for _ in range(400):
            if not vad.monitoring:
                break
            vad.queue.put(frame)
            time.sleep(0.001)

    t = threading.Thread(target=feeder)
    t.start()
    vad._barge_watch()
    t.join(timeout=2)

    assert vad.barge_requested
    assert fired == [1]


def test_barge_watch_no_false_positive():
    class FakeBarge:
        def wake_transcribe(self, path):
            return 'texto sem o nome'

        def is_wake(self, text):
            return False

    fired = []
    vad = VADListener({}, lambda p: None, barge=FakeBarge(), on_barge_in=lambda: fired.append(1), block_ms=30)
    vad.running = True
    vad.monitoring = True
    frame = np.zeros(480, dtype='float32')

    def feeder():
        for _ in range(400):
            if not vad.monitoring:
                break
            vad.queue.put(frame)
            time.sleep(0.001)
        vad.monitoring = False

    t = threading.Thread(target=feeder)
    t.start()
    vad._barge_watch()
    t.join(timeout=2)

    assert not vad.barge_requested
    assert fired == []


def test_is_wake(tmp_path):
    from core.brain import Brain
    cfg = {
        'activation': {'type': 'vad', 'mode': 'wake_word', 'wake_words': ['sexta feira'], 'session_timeout_s': 20, 'barge_in': True},
        'stt': {'model': 'small', 'preload': False, 'wake_model': 'tiny'},
        'memory': {'dir': str(tmp_path), 'save_transcripts': False},
        'reminders': {'enabled': False},
        'llm': {'mode': 'local', 'local': {'model': 'x'}},
    }
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(cfg), encoding='utf-8')
    b = Brain(config_path=path)
    assert b.barge_enabled
    assert b.is_wake('Sexto Freira, oi')
    assert b.is_wake('sexta feira')
    assert not b.is_wake('abre o youtube')
    assert not b.is_wake('')
