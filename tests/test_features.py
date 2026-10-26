import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.commands import (
    Commands, parse_reminder_time, pt_number_in_text,
    _strip_reminder_text, format_reminder,
)
from core.memory import Memory
from core.websearch import looks_like_knowledge_question


def make_commands(config=None):
    mem = Memory({'dir': tempfile.mkdtemp(), 'save_transcripts': False})
    return Commands(memory=mem, config=config or {}), mem


def test_pt_numbers():
    assert pt_number_in_text('volume sessenta') == 60
    assert pt_number_in_text('som em cinco') == 5
    assert pt_number_in_text('cem por cento') == 100
    assert pt_number_in_text('nada aqui') is None


def test_reminder_parse_relative_days():
    now = datetime(2026, 10, 26, 19, 0)  # segunda-feira
    t = parse_reminder_time('me lembra de comprar leite amanha as 9', now=now)
    assert t == now.replace(day=27, hour=9, minute=0, second=0, microsecond=0)
    t2 = parse_reminder_time('lembre de ir ao medico hoje as 15h30', now=now)
    assert t2.hour == 15 and t2.minute == 30 and t2.day == 27
    t3 = parse_reminder_time('avisar segunda feira as 10', now=now)
    assert t3.day == 2 and t3.hour == 10


def test_reminder_parse_no_time_weekday():
    now = datetime(2026, 10, 26, 19, 0)
    t = parse_reminder_time('lembra amanha', now=now)
    assert t is not None and t.hour == 10


def test_reminder_parse_invalid():
    now = datetime(2026, 10, 26, 19, 0)
    assert parse_reminder_time('lembra as 99h', now=now) is None


def test_strip_reminder_text():
    task = _strip_reminder_text('me lembra de comprar leite amanha as 9')
    assert 'comprar leite' in task
    assert 'amanha' not in task and 'as 9' not in task


def test_reminder_command_end_to_end():
    c, mem = make_commands()
    r = c.run('me lembra de comprar leite amanha as 9')
    assert r.name == 'reminder'
    assert 'comprar leite' in r.response
    items = mem._read_reminders()
    assert len(items) == 1
    assert 'comprar leite' in items[0]['text']
    when = datetime.fromisoformat(items[0]['when'])
    assert when.hour == 9


def test_reminder_due():
    mem = Memory({'dir': tempfile.mkdtemp(), 'save_transcripts': False})
    past = '2020-01-01T00:00:00'
    future = '2099-01-01T00:00:00'
    mem.add_reminder(past, 'antigo')
    mem.add_reminder(future, 'futuro')
    due = mem.due_reminders('2026-01-01T00:00:00')
    assert len(due) == 1 and due[0]['text'] == 'antigo'
    assert mem.count_reminders() == 1


def test_knowledge_detection():
    assert looks_like_knowledge_question('quem e o presidente do brasil')
    assert looks_like_knowledge_question('o que e fotossintese')
    assert looks_like_knowledge_question('quando surgiu a internet')
    assert not looks_like_knowledge_question('que horas sao')
    assert not looks_like_knowledge_question('abre o youtube')


def test_volume_words(monkeypatch):
    calls = {}
    monkeypatch.setattr('core.commands._wpctl', lambda *a: calls.setdefault('args', a) or 'Volume: 0.60')
    c, _ = make_commands()
    r = c.run('volume sessenta')
    assert r.name == 'volume'
    assert '60' in r.response


def test_brain_with_websearch_mock(tmp_path):
    from core.brain import Brain
    import core.websearch as ws

    cfg = {
        'activation': {'type': 'vad', 'mode': 'wake_word', 'wake_words': ['sexta feira'], 'session_timeout_s': 20},
        'stt': {'model': 'small', 'preload': False},
        'memory': {'dir': str(tmp_path), 'save_transcripts': False},
        'reminders': {'enabled': False},
        'web_search': {'enabled': True},
        'llm': {'mode': 'local', 'local': {'model': 'x'}},
    }
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(cfg), encoding='utf-8')
    b = Brain(config_path=path)
    captured = {}
    class P:
        model = 'x'
        def chat(self, messages, **k):
            captured['system'] = messages[0]['content']
            return 'ok'
    b.llm = P()
    b.think('quem e o presidente do brasil')
    assert 'president' in captured['system'] or 'Data e hora' in captured['system']
    assert 'voz alta' in captured['system']
