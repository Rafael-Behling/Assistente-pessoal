import json
import tempfile
import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.brain import Brain


def make_brain(tmp_path, **overrides):
    cfg = {
        'activation': {
            'type': 'vad', 'mode': 'wake_word',
            'wake_words': ['sexta feira'], 'session_timeout_s': 20,
        },
        'stt': {'model': 'small', 'preload': False},
        'memory': {'dir': str(tmp_path), 'save_transcripts': False},
        'llm': {'mode': 'local', 'local': {'model': 'x'}},
    }
    cfg.update(overrides)
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(cfg), encoding='utf-8')
    return Brain(config_path=path)


class FakeSTT:
    model_size = 'fake'
    language = 'pt'
    beam_size = 1
    model = object()

    def __init__(self, text):
        self.text = text
        self.calls = []

    def load_model(self):
        pass

    def transcribe(self, audio_path, language=None, initial_prompt=None, delete=True):
        self.calls.append({'initial_prompt': initial_prompt, 'delete': delete})
        return self.text


class FakeStreamProvider:
    model = 'fake'

    def __init__(self, chunks):
        self.chunks = chunks

    def chat(self, messages, **kwargs):
        return ''.join(self.chunks)

    def chat_stream(self, messages, **kwargs):
        yield from self.chunks


def test_two_pass_wake(tmp_path, monkeypatch):
    b = make_brain(tmp_path)
    fake = FakeSTT('sexta feira que horas sao')
    b.stt_wake = fake
    b.stt = FakeSTT('Sexta-Feira, que horas são?')
    outcome = b.handle_utterance('fake.wav')
    assert outcome is not None
    transcript, query, response = outcome
    assert 'horas' in query
    assert fake.calls[0]['delete'] is False
    assert fake.calls[0]['initial_prompt']
    assert b.last_stt_s >= 0


def test_two_pass_ignores_without_wake(tmp_path, monkeypatch):
    b = make_brain(tmp_path)
    b.stt_wake = FakeSTT('abre o youtube')
    b.stt = FakeSTT('abre o youtube')
    assert b.handle_utterance('fake.wav') is None


def test_cancel_stops_stream(tmp_path):
    b = make_brain(tmp_path)

    chunks = ['Primeira frase. ', 'Segunda frase. ', 'Terceira frase. ']

    class StopProvider(FakeStreamProvider):
        def chat_stream(self, messages, **kwargs):
            yield from self.chunks

    spoken = []
    def on_sentence(s):
        spoken.append(s)
        b._cancelled = True

    b.llm = StopProvider(chunks)
    resp = b.think('fale muito', on_sentence=on_sentence)
    assert spoken == ['Primeira frase.']
    assert resp == 'Primeira frase.'


def test_history_in_session(tmp_path):
    b = make_brain(tmp_path)
    b.llm = FakeStreamProvider(['resposta.'])
    b.think('primeira')
    assert len(b.history) == 2
    b.think('segunda')
    assert len(b.history) == 4
    assert b.history[0]['content'] == 'primeira'
    assert b.history[-1]['content'] == 'resposta.'


def test_history_capped(tmp_path):
    b = make_brain(tmp_path)
    for i in range(10):
        b._push_history(f'u{i}', f'a{i}')
    assert len(b.history) == 10
    assert b.history[0]['content'] == 'u5'


def test_session_open_reflects_wake(tmp_path):
    b = make_brain(tmp_path)
    assert not b.session_open()
    b.session_open_until = time.monotonic() + 5
    assert b.session_open()
    b2 = make_brain(tmp_path, activation={'type': 'vad', 'mode': 'always_on'})
    assert b2.session_open()
