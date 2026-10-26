import json
import re
import shutil
import subprocess
import threading
import time
import unicodedata
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

import httpx


class CommandResult:
    def __init__(self, name, response):
        self.name = name
        self.response = response


def normalize(text):
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def _run(args):
    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _xdg_dir(key, fallback):
    try:
        out = subprocess.check_output(['xdg-user-dir', key], text=True, timeout=3).strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return Path.home() / fallback


WEEKDAYS = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']
MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

CATEGORIES = [
    ('Imagens', {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.heic', '.tiff', '.ico'}),
    ('Documentos', {'.pdf', '.doc', '.docx', '.odt', '.txt', '.md', '.rtf', '.epub', '.tex'}),
    ('Planilhas', {'.xls', '.xlsx', '.ods', '.csv'}),
    ('Apresentações', {'.ppt', '.pptx', '.odp'}),
    ('Vídeos', {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.flv'}),
    ('Músicas', {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.opus'}),
    ('Compactados', {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.zst'}),
    ('Código', {'.py', '.sh', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.scss', '.json', '.yaml', '.yml', '.toml', '.c', '.cpp', '.h', '.hpp', '.java', '.rs', '.go', '.rb', '.php', '.sql'}),
]

FOLDERS = {
    'downloads': ('DOWNLOAD', 'Downloads'),
    'documentos': ('DOCUMENTS', 'Documentos'),
    'imagens': ('PICTURES', 'Imagens'),
    'fotos': ('PICTURES', 'Imagens'),
    'musicas': ('MUSIC', 'Músicas'),
    'videos': ('VIDEOS', 'Vídeos'),
    'area de trabalho': ('DESKTOP', 'Área de Trabalho'),
    'desktop': ('DESKTOP', 'Área de Trabalho'),
    'home': ('HOME', 'pasta pessoal'),
    'pasta pessoal': ('HOME', 'pasta pessoal'),
}

BROWSERS = {
    'chrome': ['google-chrome-stable', 'google-chrome', 'chromium', 'chromium-browser'],
    'firefox': ['firefox'],
    'brave': ['brave-browser', 'brave'],
    'chromium': ['chromium', 'chromium-browser'],
    'edge': ['microsoft-edge-stable', 'microsoft-edge'],
    'opera': ['opera'],
    'vivaldi': ['vivaldi-stable', 'vivaldi'],
}

SITES = {
    'google': ('https://www.google.com', 'Google'),
    'youtube': ('https://www.youtube.com', 'YouTube'),
    'github': ('https://github.com', 'GitHub'),
    'gmail': ('https://mail.google.com', 'Gmail'),
    'whatsapp': ('https://web.whatsapp.com', 'WhatsApp'),
    'instagram': ('https://www.instagram.com', 'Instagram'),
    'facebook': ('https://www.facebook.com', 'Facebook'),
    'twitter': ('https://twitter.com', 'Twitter'),
    'chatgpt': ('https://chatgpt.com', 'ChatGPT'),
    'netflix': ('https://www.netflix.com', 'Netflix'),
    'maps': ('https://maps.google.com', 'Google Maps'),
    'drive': ('https://drive.google.com', 'Google Drive'),
    'reddit': ('https://www.reddit.com', 'Reddit'),
    'linkedin': ('https://www.linkedin.com', 'LinkedIn'),
    'twitch': ('https://www.twitch.tv', 'Twitch'),
}

APPS = {
    'calculadora': ['gnome-calculator', 'kcalc', 'qalculate-gtk', 'galculator'],
    'terminal': ['foot', 'kitty', 'alacritty', 'gnome-terminal', 'konsole', 'xterm'],
    'arquivos': ['nautilus', 'dolphin', 'thunar', 'pcmanfm'],
    'gerenciador de arquivos': ['nautilus', 'dolphin', 'thunar', 'pcmanfm'],
    'configuracoes': ['gnome-control-center', 'systemsettings', 'xfce4-settings-manager'],
    'editor': ['code', 'codium', 'gedit', 'kate', 'xed'],
    'vscode': ['code', 'codium'],
    'code': ['code', 'codium'],
    'spotify': ['spotify'],
    'steam': ['steam'],
    'discord': ['discord'],
    'telegram': ['telegram-desktop', 'telegram'],
    'whatsapp': ['whatsapp-for-linux', 'whatsapp-desktop', 'whatsdesk'],
    'obs': ['obs'],
    'obs studio': ['obs'],
    'gimp': ['gimp'],
    'libreoffice': ['libreoffice'],
}

HELP_TEXT = (
    'Posso ver as horas e a data, o clima, abrir o navegador, pesquisar na web, abrir pastas e aplicativos, '
    'organizar a área de trabalho, controlar o volume e a música, tirar capturas de tela, definir timers, '
    'ler notícias, anotar coisas que você me diz e bloquear a tela.'
)


PT_NUMBERS = {
    'zero': 0, 'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'tres': 3, 'quatro': 4, 'cinco': 5,
    'seis': 6, 'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10, 'onze': 11, 'doze': 12,
    'treze': 13, 'quatorze': 14, 'catorze': 14, 'quinze': 15, 'dezesseis': 16,
    'dezessete': 17, 'dezoito': 18, 'dezenove': 19,
    'vinte': 20, 'trinta': 30, 'quarenta': 40, 'cinquenta': 50, 'sessenta': 60,
    'setenta': 70, 'oitenta': 80, 'noventa': 90, 'cem': 100,
}


def pt_number_in_text(text):
    for word, value in PT_NUMBERS.items():
        if re.search(rf'\b{word}\b', text):
            return value
    return None


def parse_reminder_time(q, now=None):
    now = now or datetime.now()
    day = 0
    if re.search(r'\bamanha\b', q):
        day = 1
    else:
        for i, wd in enumerate(WEEKDAYS):
            if re.search(rf'\b{wd}\b', q):
                day = (i - now.weekday()) % 7
                if day == 0:
                    day = 7
                break
    hh = mm = None
    m = re.search(r'\bas\s+(\d{1,2})(?:h\s*(\d{2})?|:\s*(\d{2}))?', q)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2) or m.group(3) or 0)
    if hh is None:
        m = re.search(r'\b(\d{1,2})\s*h(?:\s*(\d{2}))?\b', q)
        if m:
            hh, mm = int(m.group(1)), int(m.group(2) or 0)
    if hh is None:
        m = re.search(r'\b(\d{1,2}):(\d{2})\b', q)
        if m:
            hh, mm = int(m.group(1)), int(m.group(2))
    if hh is None and day:
        if 'de manha' in q:
            hh, mm = 9, 0
        elif 'de tarde' in q:
            hh, mm = 15, 0
        elif 'de noite' in q:
            hh, mm = 20, 0
        else:
            hh, mm = 10, 0
    if hh is None or not 0 <= hh <= 23 or mm is None or not 0 <= mm <= 59:
        return None
    target = (now + timedelta(days=day)).replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        if day:
            return None
        target += timedelta(days=1)
    return target


def format_reminder(target):
    day_word = 'hoje' if target.date() == datetime.now().date() else 'amanhã'
    return f'{day_word} às {target.hour}h{target.minute:02d}'


def _strip_reminder_text(q):
    task = q
    m = re.search(r'\b(?:lembra|lembrar|avisa|avisar|lembre|recorde)(?:\s+(?:de|que|para|pra|a|sobre))?\s*(.+)$', task)
    if m:
        task = m.group(1)
    task = re.sub(
        r'\b(?:hoje|amanha|de manha|de tarde|de noite|segunda|terca|quarta|quinta|sexta|sabado|domingo|'
        r'as?\s*\d{1,2}(?::\d{2})?|as?\s*\d{1,2}\s*h(?:\s*\d{2})?|horas?|hora|daqui a|dia \d{1,2})\b',
        ' ', task,
    )
    return re.sub(r'\s+', ' ', task).strip(' ,.!?;:')


def format_time(now=None):
    now = now or datetime.now()
    h, m = now.hour, now.minute
    if h == 0:
        base = 'meia-noite'
    elif h == 1:
        base = '1 hora'
    else:
        base = f'{h} horas'
    prefix = 'Agora é' if h <= 1 else 'Agora são'
    if m == 0:
        return f'{prefix} {base} em ponto.'
    if m == 1:
        return f'{prefix} {base} e 1 minuto.'
    return f'{prefix} {base} e {m} minutos.'


def format_date(now=None):
    now = now or datetime.now()
    return f'Hoje é {WEEKDAYS[now.weekday()]}, {now.day} de {MONTHS[now.month - 1]} de {now.year}.'


def _category_for(suffix):
    suffix = suffix.lower()
    for name, extensions in CATEGORIES:
        if suffix in extensions:
            return name
    return 'Outros'


def _unique_path(dest):
    if not dest.exists():
        return dest
    i = 1
    while True:
        candidate = dest.with_name(f'{dest.stem} ({i}){dest.suffix}')
        if not candidate.exists():
            return candidate
        i += 1


def _desktop_path():
    path = _xdg_dir('DESKTOP', 'Desktop')
    if path.exists():
        return path
    alt = Path.home() / 'Área de Trabalho'
    if alt.exists():
        return alt
    return path


def organize_directory(directory):
    directory = Path(directory)
    if not directory.exists():
        return 'Não encontrei a pasta da área de trabalho.'
    counts = {}
    errors = 0
    total = 0
    for entry in list(directory.iterdir()):
        if not entry.is_file() or entry.is_symlink():
            continue
        if entry.name.startswith('.') or entry.suffix.lower() == '.desktop':
            continue
        category = _category_for(entry.suffix)
        target_dir = directory / category
        try:
            target_dir.mkdir(exist_ok=True)
            dest = _unique_path(target_dir / entry.name)
            shutil.move(str(entry), str(dest))
            counts[category] = counts.get(category, 0) + 1
            total += 1
        except Exception as e:
            print(f'[COMMANDS] Erro ao mover {entry}: {e}')
            errors += 1
    if total == 0 and errors == 0:
        return 'Sua área de trabalho já está organizada.'
    order = [name for name, _ in CATEGORIES] + ['Outros']
    parts = [f'{counts[category]} em {category}' for category in order if category in counts]
    response = f'Organizei {total} arquivo' + ('' if total == 1 else 's') + ' na área de trabalho'
    if parts:
        response += ': ' + ', '.join(parts)
    response += '.'
    if errors:
        response += f' Não consegui mover {errors} arquivo' + ('' if errors == 1 else 's') + '.'
    return response


def _search_query(original, q):
    m = re.search(r'\b(?:pesquis\w*|procur\w*|busc\w*)\s+(?:por\s+|sobre\s+)?(.+?)(?:\s+(?:no|na)\s+(?:google|internet|web))?$', q)
    if m:
        query = m.group(1).strip()
        if query and query not in ('no google', 'na internet', 'na web', 'google', 'internet', 'web'):
            return query
    m = re.search(r'\bgoogle\s+(.+)$', q)
    if m:
        return m.group(1).strip()
    return ''


def _browser_exe(q):
    for name, exes in BROWSERS.items():
        if re.search(rf'\b{name}\b', q):
            for exe_name in exes:
                exe = shutil.which(exe_name)
                if exe:
                    return name, exe
            return name, None
    return None, None


def _open_url(url, browser_exe=None):
    if browser_exe:
        _run([browser_exe, url])
        return
    xdg = shutil.which('xdg-open')
    if xdg:
        _run([xdg, url])
    else:
        webbrowser.open(url)


def _wpctl(*args):
    return subprocess.check_output(['wpctl', *args], text=True, timeout=3).strip()


def _volume_percent():
    out = _wpctl('get-volume', '@DEFAULT_AUDIO_SINK@')
    m = re.search(r'Volume:\s+([0-9.]+)', out)
    if m:
        return round(float(m.group(1)) * 100)
    return None


def _desktop_dirs():
    dirs = [
        Path.home() / '.local/share/applications',
        Path('/usr/share/applications'),
        Path('/usr/local/share/applications'),
        Path('/var/lib/flatpak/exports/share/applications'),
        Path.home() / '.local/share/flatpak/exports/share/applications',
    ]
    return [d for d in dirs if d.exists()]


def _desktop_entries():
    for directory in _desktop_dirs():
        for path in directory.rglob('*.desktop'):
            try:
                text = path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            if re.search(r'^(?:NoDisplay|Hidden)=true\s*$', text, re.M | re.I):
                continue
            names = []
            for line in text.splitlines():
                if line.startswith('Name=') or line.startswith('Name[pt_BR]=') or line.startswith('Name[pt]='):
                    names.append(line.split('=', 1)[1].strip())
            if not names:
                continue
            desktop_id = str(path.relative_to(directory)).replace('/', '-')
            if desktop_id.endswith('.desktop'):
                desktop_id = desktop_id[:-8]
            yield desktop_id, path, names


def _find_desktop_app(name):
    name = normalize(name)
    best = None
    best_score = 0
    for desktop_id, path, names in _desktop_entries():
        for candidate in names:
            c = normalize(candidate)
            if c == name:
                score = 100
            elif len(c) >= 3 and (c.startswith(name) or name.startswith(c)):
                score = 80
            elif len(c) >= 3 and len(name) >= 3 and (name in c or c in name):
                score = 60
            else:
                continue
            if score > best_score:
                best_score = score
                best = (desktop_id, path, candidate)
    return best


def _launch_desktop(desktop_id, path):
    try:
        result = subprocess.run(['gtk-launch', desktop_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        if result.returncode == 0:
            return True
    except Exception:
        pass
    try:
        result = subprocess.run(['gio', 'launch', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        return result.returncode == 0
    except Exception:
        return False


def _screenshot_tool():
    for tool in ('grim', 'spectacle', 'flameshot', 'gnome-screenshot', 'scrot'):
        path = shutil.which(tool)
        if path:
            return tool, path
    return None, None


class Commands:
    def __init__(self, memory=None, config=None):
        self.memory = memory
        self.config = config or {}
        self._items = []
        self._register()

    def _add(self, name, patterns, handler):
        self._items.append((name, [re.compile(p) for p in patterns], handler))

    def _register(self):
        self._add('time', [
            r'\b(?:que horas|que hora|horas sao|ver as horas|me (?:diga|diz|fala) as horas|hora agora|horario agora|horas agora|qual (?:e )?o horario)\b',
            r'\b(?:que dia|qual (?:e )?o dia|qual (?:e )?a data|data de hoje|dia de hoje|que data)\b',
            r'\b(?:em que (?:dia|data|mes|ano)|que (?:dia|data|mes|ano)) (?:da semana )?(?:e|estamos|hoje|hj)\b',
            r'\b(?:dia|data|mes|ano) (?:de )?(?:hoje|hj)\b',
            r'\b(?:mes|ano|data) atual\b',
            r'\b(?:que dia da semana|qual (?:e )?o dia da semana)\b',
            r'\b(?:que mes|qual (?:e )?o mes|que ano|qual (?:e )?o ano|em que ano estamos|em que mes estamos)\b',
            r'\bquantos dias (?:tem|faltam)\b',
        ], self.cmd_time)

        self._add('organize_desktop', [
            r'\b(?:organiz\w*|arrum\w*|separar|separa)\b.*\b(?:area de trabalho|desktop|mesa)\b',
            r'\b(?:area de trabalho|desktop)\b.*\b(?:organiz\w*|arrum\w*)\b',
        ], self.cmd_organize)

        self._add('open_folder', [
            r'\b(?:abrir|abre|abra|mostrar|mostra|exibir|exibe|acessar|acesse|procur\w*)\b.*\b(?:pasta|diretorio|downloads|documentos|imagens|fotos|musicas|videos|area de trabalho|desktop|home)\b',
        ], self.cmd_open_folder)

        self._add('open_browser', [
            r'\b(?:abrir|abre|abra|iniciar|inicie|entrar|entra|ir para|vai para|acessar|acesse)\b.*\b(?:navegador|browser|internet)\b',
            r'\b(?:pesquis\w*|procur\w*|busc\w*)\b',
            rf'\b(?:abrir|abre|abra|entrar|acessar|ir para)\b.*\b(?:{"|".join(re.escape(k) for k in SITES)})\b',
            r'\b(?:abrir|abre|abra|iniciar|inicie)\b.*\b(?:chrome|firefox|brave|chromium|edge|opera|vivaldi)\b',
            r'\b(?:abrir|abre|abra|acessar|acesse)\b.*(?:https?://|www\.)',
            r'\b(?:abrir|abre|abra)\b.*\b(?:site|pagina)\b',
        ], self.cmd_browser)

        self._add('screenshot', [
            r'\b(?:tirar|tira|fazer|faz|capturar|captura|print|screenshot)\b.*\b(?:print|screenshot|captura|tela)\b',
            r'\b(?:print|screenshot)\b',
        ], self.cmd_screenshot)

        self._add('lock', [
            r'\b(?:bloquear|bloqueia|trancar|tranca|lock)\b.*\b(?:tela|sessao|computador)\b',
        ], self.cmd_lock)

        self._add('volume', [
            r'\b(?:aument\w*|subi\w*|diminui\w*|baix\w*|reduz\w*)\b.*\b(?:volume|som)\b',
            r'\b(?:volume|som)\b.*\b(?:aument\w*|subi\w*|diminui\w*|baix\w*|reduz\w*)\b',
            r'\b(?:silenci\w*|mutar|mudo|sem som|dessilenci\w*|desmutar)\b',
            r'\b(?:volume|som)\b.*\d',
            r'\b(?:volume|som)\b.*\b(?:zero|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|cem)\b',
            r'\b(?:zero|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|cem)\b.*\b(?:volume|som)\b',
        ], self.cmd_volume)

        self._add('weather', [
            r'\b(?:como (?:esta|ta|vai ser)|qual (?:e )?)\s*(?:o\s+)?(?:tempo|clima)\b',
            r'\b(?:previsao (?:do tempo)?|vai chover|esta chovendo|ta chovendo)\b',
            r'\btemperatura\b',
            r'\b(?:fazer calor|fazer frio|tá calor|tá frio|frio ai|calor ai)\b',
        ], self.cmd_weather)

        self._add('timer', [
            r'\b(?:timer|cronometro|temporizador|alarme|aviso)\b',
            r'\b(?:me )?avis\w*\b.*\b(?:em|daqui)\b',
            r'\bdaqui (?:a )?\d+\s*(?:segundos?|minutos?|horas?)\b',
        ], self.cmd_timer)

        self._add('reminder', [
            r'\b(?:lembra|lembrar|avisa|avisar|lembre me|lembre-me|recorde)\b.*\b(?:amanha|hoje|segunda|terca|quarta|quinta|sexta|sabado|domingo)\b',
            r'\b(?:amanha|hoje)\s+(?:as|a)?\s*\d{1,2}(?:h|:|\s*horas?)',
            r'\b(?:lembra|avisar|lembre)\b.*\bas\s*\d{1,2}',
        ], self.cmd_reminder)

        self._add('media', [
            r'\b(?:paus\w*|despaus\w*|parar|continuar|tocar|play|proxim\w*|pular|avanca)\b.*\b(?:musica|som|video|media|spotify|player|track)\b',
            r'\b(?:musica|som|video|media|player|spotify)\b.*\b(?:paus\w*|parar|toc\w*|proxim\w*|pular|avanca)\b',
            r'\b(?:paus\w*|despaus\w*|tocar|play|proxim\w*|pular)\b',
        ], self.cmd_media)

        self._add('news', [
            r'\b(?:noticias|manchetes|novidades|o que esta acontecendo)\b',
        ], self.cmd_news)

        self._add('remember', [
            r'\b(?:lembre(?:-se)?(?:\s+(?:que|de))?|grava(?: que)?|anota(?: que)?|meu nome e|me chamo)\b',
        ], self.cmd_remember)

        self._add('recall', [
            r'\b(?:o que voce sabe sobre mim|minhas informacoes|o que voce lembra de mim|o que sabe de mim)\b',
        ], self.cmd_recall)

        self._add('forget', [
            r'\b(?:esquece tudo|esqueca tudo|apague tudo|limpe suas informacoes|apaga suas informacoes)\b',
        ], self.cmd_forget)

        self._add('open_app', [
            r'\b(?:abrir|abre|abra|iniciar|inicie|executar|execute|rodar|roda)\b\s+(?:o|a|os|as)?\s*.+',
        ], self.cmd_open_app)

        self._add('help', [
            r'\b(?:o que voce pode fazer|quais comandos|comandos disponiveis|ajud(?:a|ar|e))\b',
        ], self.cmd_help)

    def run(self, text):
        original = (text or '').strip()
        if not original:
            return None
        q = normalize(original)
        for name, patterns, handler in self._items:
            if not any(p.search(q) for p in patterns):
                continue
            if name not in ('time', 'help') and re.search(r'\b(?:nao|nunca|pare de|deixa de)\b', q):
                return None
            try:
                response = handler(original, q)
            except Exception as e:
                print(f'[COMMANDS] Erro em {name}: {e}')
                response = f'Não consegui executar o comando: {e}'
            return CommandResult(name, response)
        return None

    def cmd_time(self, original, q):
        now = datetime.now()
        wants_time = bool(re.search(r'\b(?:hora|horas|horario)\b', q))
        wants_month = bool(re.search(r'\b(?:mes|meses)\b', q))
        wants_year = bool(re.search(r'\bano\b', q))
        wants_date = bool(re.search(r'\b(?:dia|data|semana)\b', q))
        if wants_year and not wants_month:
            return f'Estamos no ano de {now.year}.'
        if wants_month:
            return f'Estamos em {MONTHS[now.month - 1]} de {now.year}.'
        if wants_date and not wants_time:
            return format_date(now)
        if wants_time and not wants_date:
            return format_time(now)
        return f'{format_time(now)} {format_date(now)}'

    def cmd_organize(self, original, q):
        return organize_directory(_desktop_path())

    def cmd_open_folder(self, original, q):
        key = None
        for name in sorted(FOLDERS, key=len, reverse=True):
            if re.search(rf'\b{re.escape(name)}\b', q):
                key = name
                break
        if key is None:
            return 'Qual pasta você quer abrir?'
        xdg_key, label = FOLDERS[key]
        path = Path.home() if xdg_key == 'HOME' else _xdg_dir(xdg_key, label)
        if not path.exists():
            return f'Não encontrei a pasta {label}.'
        _run(['xdg-open', str(path)])
        return f'Abrindo a pasta {label}.'

    def cmd_browser(self, original, q):
        browser_name, browser_exe = _browser_exe(q)

        url_match = re.search(r'(https?://\S+|www\.\S+)', original, re.IGNORECASE)
        if url_match:
            url = url_match.group(1)
            if not url.lower().startswith('http'):
                url = 'https://' + url
            _open_url(url, browser_exe)
            return f'Abrindo {url}.'

        if re.search(r'\b(?:pesquis\w*|procur\w*|busc\w*)\b', q):
            query = _search_query(original, q)
            if not query:
                return 'O que você quer pesquisar?'
            _open_url('https://www.google.com/search?q=' + quote_plus(query), browser_exe)
            return f'Pesquisando por {query}.'

        if browser_name:
            if browser_exe:
                _run([browser_exe])
                return f'Abrindo o {browser_name.title()}.'
            _open_url('https://www.google.com')
            return f'Não encontrei o {browser_name.title()}, abri o navegador padrão.'

        for name, (url, display) in SITES.items():
            if re.search(rf'\b{name}\b', q):
                _open_url(url)
                return f'Abrindo o {display}.'

        _open_url('https://www.google.com')
        return 'Abrindo o navegador.'

    def cmd_volume(self, original, q):
        try:
            if re.search(r'\b(?:dessilenci\w*|desmutar|tirar o mudo|voltar o som)\b', q):
                _wpctl('set-mute', '@DEFAULT_AUDIO_SINK@', '0')
                return 'Som ativado.'
            if re.search(r'\b(?:silenci\w*|mutar|mudo|sem som)\b', q):
                _wpctl('set-mute', '@DEFAULT_AUDIO_SINK@', '1')
                return 'Som silenciado.'
            if re.search(r'\b(?:aument\w*|subi\w*)\b.*\b(?:volume|som)\b', q) or re.search(r'\b(?:volume|som)\b.*\b(?:aument\w*|subi\w*)\b', q):
                _wpctl('set-volume', '@DEFAULT_AUDIO_SINK@', '5%+')
                pct = _volume_percent()
                return f'Volume em {pct}%.' if pct is not None else 'Volume aumentado.'
            if re.search(r'\b(?:diminui\w*|baix\w*|reduz\w*)\b.*\b(?:volume|som)\b', q) or re.search(r'\b(?:volume|som)\b.*\b(?:diminui\w*|baix\w*|reduz\w*)\b', q):
                _wpctl('set-volume', '@DEFAULT_AUDIO_SINK@', '5%-')
                pct = _volume_percent()
                return f'Volume em {pct}%.' if pct is not None else 'Volume diminuído.'
            exact = re.search(r'\b(?:volume|som)\b\s*(?:para|em|a)?\s*(\d{1,3})\s*%?', q)
            if not exact:
                num = pt_number_in_text(q)
                if num is not None:
                    exact_num = f'{num}'
                    value = max(0, min(100, num))
                    _wpctl('set-volume', '@DEFAULT_AUDIO_SINK@', f'{value}%')
                    return f'Volume em {value}%.'
            if exact:
                value = max(0, min(100, int(exact.group(1))))
                _wpctl('set-volume', '@DEFAULT_AUDIO_SINK@', f'{value}%')
                return f'Volume em {value}%.'
            return 'O que você quer fazer com o volume?'
        except Exception:
            return 'Não consegui controlar o volume.'

    def cmd_open_app(self, original, q):
        m = re.search(r'\b(?:abrir|abre|abra|iniciar|inicie|executar|execute|rodar|roda)\b\s+(?:o|a|os|as)?\s*(.+)$', q)
        if not m:
            return 'Qual aplicativo você quer abrir?'
        name = m.group(1)
        name = re.sub(r'\b(?:pra mim|para mim|por favor|agora|aqui)\b', '', name).strip(' .!?')
        name = re.sub(r'^(?:site|pagina)\s+', '', name)
        name = re.sub(r'^(?:app|aplicativo|programa)\s+', '', name)
        if not name:
            return 'Qual aplicativo você quer abrir?'
        exes = APPS.get(name)
        if not exes:
            for key, value in APPS.items():
                if name.startswith(key) or key.startswith(name):
                    exes = value
                    name = key
                    break
        if exes:
            for exe_name in exes:
                exe = shutil.which(exe_name)
                if exe:
                    _run([exe])
                    return f'Abrindo {name.capitalize()}.'
        found = _find_desktop_app(name)
        if found:
            desktop_id, path, display = found
            if _launch_desktop(desktop_id, path):
                return f'Abrindo {display}.'
        return f'Não encontrei o aplicativo {name}.'

    def cmd_weather(self, original, q):
        location = (self.config.get('weather') or {}).get('location', '')
        url = f'https://wttr.in/{quote_plus(location)}?format=j1&lang=pt' if location else 'https://wttr.in/?format=j1&lang=pt'
        try:
            r = httpx.get(url, timeout=8, headers={'User-Agent': 'curl/8'})
            r.raise_for_status()
            data = r.json()
            cur = data['current_condition'][0]
            desc = (cur.get('lang_pt') or [{}])[0].get('value') or (cur.get('weatherDesc') or [{}])[0].get('value', '')
            today = data['weather'][0]
            resp = f'{desc}: {cur["temp_C"]} graus, sensação de {cur["FeelsLikeC"]}. Máxima {today["maxtempC"]}, mínima {today["mintempC"]}, umidade {cur["humidity"]}%.'
            return f'Em {location}, {resp}' if location else resp
        except Exception as e:
            print(f'[COMMANDS] Erro no clima: {e}')
            return 'Não consegui pegar a previsão do tempo.'

    def cmd_timer(self, original, q):
        m = re.search(r'(\d+)\s*(segundos?|minutos?|horas?)', q)
        if not m:
            return 'Quanto tempo você quer no timer?'
        n = int(m.group(1))
        unit = m.group(2)
        seconds = n * (3600 if unit.startswith('hora') else 60 if unit.startswith('minuto') else 1)
        if seconds < 1 or seconds > 86400:
            return 'Esse tempo é estranho. Tente outro.'
        label = f'{n} {unit}'
        def ring():
            try:
                _run(['notify-send', '-a', 'Sexta-Feira', 'Sexta-Feira', f'Tempo esgotado: {label}'])
            except Exception:
                pass
            print(f"[TIMER] Tempo esgotado: {label}")
        timer = threading.Timer(seconds, ring)
        timer.daemon = True
        timer.start()
        return f'Ok, aviso em {label}.'

    def cmd_media(self, original, q):
        exe = shutil.which('playerctl')
        if not exe:
            return 'playerctl não está instalado.'
        if re.search(r'\b(?:proxim\w*|pular|avanca)\b', q):
            action, msg = 'next', 'Próxima.'
        elif re.search(r'\b(?:paus\w*|parar)\b', q):
            action, msg = 'pause', 'Pausado.'
        elif re.search(r'\b(?:tocar|play|continuar|despaus\w*)\b', q):
            action, msg = 'play', 'Tocando.'
        else:
            action, msg = 'play-pause', 'Alternado.'
        try:
            subprocess.run([exe, action], timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return msg
        except Exception:
            return 'Não consegui controlar o player.'

    def cmd_news(self, original, q):
        try:
            r = httpx.get('https://g1.globo.com/rss/g1/', timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
            r.raise_for_status()
            root = ET.fromstring(r.content)
            titles = [i.findtext('title', '').strip() for i in root.iter('item')][:4]
            titles = [t for t in titles if t]
            if not titles:
                return 'Não encontrei notícias agora.'
            return 'Manchetes: ' + ' | '.join(titles)
        except Exception as e:
            print(f'[COMMANDS] Erro nas notícias: {e}')
            return 'Não consegui buscar as notícias.'

    def cmd_remember(self, original, q):
        m = re.search(r'\b(?:lembre(?:-se)?(?:\s+(?:que|de))?|grava(?: que)?|anota(?: que)?|meu nome e|me chamo)\b\s*(.+)$', q)
        fact = (m.group(1) if m else '').strip(' ,.!?;:')
        if not fact:
            return 'O que você quer que eu anote?'
        if re.search(r'\b(?:meu nome e|me chamo)\b', q):
            fact = f'O nome do usuário é {fact}.'
        if self.memory:
            self.memory.remember_fact(fact)
            return 'Anotado.'
        return 'Não tenho memória disponível.'

    def cmd_recall(self, original, q):
        facts = self.memory.load_facts() if self.memory else []
        if not facts:
            return 'Ainda não anotei nada sobre você.'
        return 'Lembrando: ' + ' '.join(facts)

    def cmd_forget(self, original, q):
        if self.memory:
            self.memory.clear_facts()
        return 'Apaguei tudo que sabia sobre você.'

    def cmd_reminder(self, original, q):
        target = parse_reminder_time(q)
        if target is None:
            return 'Para quando é o lembrete? Ex: amanhã às 9.'
        task = _strip_reminder_text(q)
        if not task:
            task = 'Você pediu para lembrar algo'
        if self.memory:
            self.memory.add_reminder(target.isoformat(timespec='seconds'), task)
            return f'Ok, lembrete para {format_reminder(target)}: {task}.'
        return 'Não tenho memória disponível para lembretes.'

    def cmd_screenshot(self, original, q):
        tool, path = _screenshot_tool()
        if not tool:
            return 'Não encontrei uma ferramenta de captura de tela.'
        out_dir = _xdg_dir('PICTURES', 'Pictures')
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = out_dir / f'Captura_{datetime.now():%Y-%m-%d_%H-%M-%S}.png'
            if tool == 'grim':
                subprocess.run([path, str(filename)], check=True, timeout=15)
            elif tool == 'spectacle':
                subprocess.run([path, '-b', '-n', '-o', str(filename)], check=True, timeout=15)
            elif tool == 'flameshot':
                subprocess.run([path, 'full', '-p', str(out_dir)], check=True, timeout=15)
            elif tool == 'gnome-screenshot':
                subprocess.run([path, '-f', str(filename)], check=True, timeout=15)
            elif tool == 'scrot':
                subprocess.run([path, str(filename)], check=True, timeout=15)
            return f'Captura salva em {out_dir.name}.'
        except Exception as e:
            print(f'[COMMANDS] Erro na captura: {e}')
            return 'Não consegui tirar a captura de tela.'

    def cmd_lock(self, original, q):
        try:
            subprocess.run(['loginctl', 'lock-session'], check=True, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 'Tela bloqueada.'
        except Exception:
            return 'Não consegui bloquear a tela.'

    def cmd_help(self, original, q):
        return HELP_TEXT
