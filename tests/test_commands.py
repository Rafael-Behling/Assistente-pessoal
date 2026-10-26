import json
import tempfile
import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.commands import Commands, organize_directory, format_time, format_date
from core.memory import Memory


def make_commands(config=None):
    mem = Memory({'dir': tempfile.mkdtemp(), 'save_transcripts': False})
    return Commands(memory=mem, config=config or {}), mem


def test_time_variants():
    c, _ = make_commands()
    assert c.run('que horas sao').name == 'time'
    assert 'horas' in c.run('que horas sao').response
    assert c.run('que dia e hoje').name == 'time'
    assert c.run('que dia hj').name == 'time'
    assert c.run('em que dia estamos').name == 'time'
    assert c.run('qual a data de hoje').name == 'time'


def test_month_and_year():
    c, _ = make_commands()
    r = c.run('que mes estamos')
    assert r.name == 'time' and 'outubro' in r.response.lower()
    r2 = c.run('que ano e')
    assert r2.name == 'time' and '2026' in r2.response


def test_format_date_and_time():
    now = format_date.__globals__['datetime'].now()
    assert 'Hoje é' in format_date(now)
    assert 'Agora' in format_time(now)


def test_organize(tmp_path):
    (tmp_path / 'foto.png').write_text('x')
    (tmp_path / 'relatorio.pdf').write_text('x')
    (tmp_path / 'musica.mp3').write_text('x')
    resp = organize_directory(tmp_path)
    assert 'Organizei 3' in resp
    assert (tmp_path / 'Imagens' / 'foto.png').exists()
    assert (tmp_path / 'Documentos' / 'relatorio.pdf').exists()
    assert (tmp_path / 'Músicas' / 'musica.mp3').exists()
    resp2 = organize_directory(tmp_path)
    assert 'já está organizada' in resp2


def test_organize_unique_names(tmp_path):
    (tmp_path / 'a.txt').write_text('1')
    (tmp_path / 'b.txt').write_text('2')
    organize_directory(tmp_path)
    (tmp_path / 'a.txt').write_text('3')
    organize_directory(tmp_path)
    assert (tmp_path / 'Documentos' / 'a (1).txt').exists()


def test_remember_and_recall():
    c, mem = make_commands()
    assert c.run('lembre que eu gosto de pizza').name == 'remember'
    assert 'pizza' in mem.load_facts()[0]
    assert c.run('meu nome e Rafael').name == 'remember'
    assert any('nome do usuário' in f for f in mem.load_facts())
    r = c.run('o que voce sabe sobre mim')
    assert 'pizza' in r.response


def test_forget():
    c, mem = make_commands()
    c.run('lembre que eu gosto de pizza')
    assert c.run('esquece tudo').name == 'forget'
    assert mem.load_facts() == []


def test_browser_search(monkeypatch):
    called = {}
    monkeypatch.setattr('core.commands._open_url', lambda url, b=None: called.setdefault('url', url))
    c, _ = make_commands()
    r = c.run('pesquisar receita de bolo')
    assert r.name == 'open_browser'
    assert 'receita' in called['url'] and 'bolo' in called['url']


def test_site_open(monkeypatch):
    called = {}
    monkeypatch.setattr('core.commands._open_url', lambda url, b=None: called.setdefault('url', url))
    c, _ = make_commands()
    assert c.run('abre o youtube').name == 'open_browser'
    assert called['url'] == 'https://www.youtube.com'


def test_open_app_not_found():
    c, _ = make_commands()
    r = c.run('abrir zzzappfake')
    assert 'Não encontrei' in r.response


def test_help():
    c, _ = make_commands()
    assert c.run('o que voce pode fazer').name == 'help'


def test_negation_blocks_command():
    c, _ = make_commands()
    assert c.run('nao abra o youtube') is None


def test_weather_patterns(monkeypatch):
    import httpx
    def boom(*a, **k):
        raise Exception('offline')
    monkeypatch.setattr(httpx, 'get', boom)
    c, _ = make_commands()
    r = c.run('como esta o tempo')
    assert r.name == 'weather'
    assert 'não consegui' in r.response.lower()


def test_timer():
    c, _ = make_commands()
    r = c.run('me avisa em 10 minutos')
    assert r.name == 'timer'
    assert '10 minutos' in r.response


def test_memory_log_and_facts():
    mem = Memory({'dir': tempfile.mkdtemp(), 'save_transcripts': True})
    mem.log_turn('oi', 'ola', stt_s=1.5, llm_s=2.0, model='test')
    files = list(mem.dir.glob('*.jsonl'))
    assert len(files) == 1
    entry = json.loads(files[0].read_text(encoding='utf-8').strip())
    assert entry['voce'] == 'oi' and entry['model'] == 'test'
    mem.remember_fact('teste fato')
    assert mem.load_facts() == ['teste fato']


def test_brain_wake_and_session(tmp_path):
    from core.brain import Brain
    cfg = {
        'activation': {
            'type': 'vad', 'mode': 'wake_word',
            'wake_words': ['sexta feira'], 'session_timeout_s': 20,
        },
        'stt': {'model': 'small', 'preload': False},
        'memory': {'dir': str(tmp_path), 'save_transcripts': False},
        'llm': {'mode': 'local', 'local': {'model': 'qwen2.5:3b'}},
    }
    cfg_path = tmp_path / 'config.json'
    cfg_path.write_text(json.dumps(cfg), encoding='utf-8')
    b = Brain(config_path=cfg_path)

    assert b.wake_enabled and not b.session_open()
    ok, q, attn = b.check_wake('Sexta-Feira, que horas são?')
    assert ok and 'horas' in q and not attn
    assert b.session_open()
    ok2, q2, _ = b.check_wake('abre o youtube')
    assert ok2 and q2 == 'abre o youtube'

    b.session_open_until = time.monotonic() - 1
    assert not b.session_open()
    ok3, _, _ = b.check_wake('qualquer coisa')
    assert not ok3

    b._push_history('a', 'b')
    b.check_wake('sexta feira')
    assert b.history == []

    b.session_open_until = time.monotonic() - 1
    ok4, _, attn4 = b.check_wake('sexta feira')
    assert ok4 and attn4
