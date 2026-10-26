import re
import shutil
import subprocess
import unicodedata
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus


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
    'Posso ver as horas e a data, abrir o navegador, pesquisar na web, abrir pastas e aplicativos, '
    'organizar a área de trabalho, controlar o volume, tirar capturas de tela e bloquear a tela.'
)


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
    def __init__(self):
        self._items = []
        self._register()

    def _add(self, name, patterns, handler):
        self._items.append((name, [re.compile(p) for p in patterns], handler))

    def _register(self):
        self._add('time', [
            r'\b(?:que horas|que hora|horas sao|ver as horas|me (?:diga|diz|fala) as horas|hora agora|horario agora|horas agora|qual (?:e )?o horario)\b',
            r'\b(?:que dia|qual (?:e )?o dia|qual (?:e )?a data|data de hoje|dia de hoje|que data)\b',
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
        ], self.cmd_volume)

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
        wants_date = bool(re.search(r'\b(?:dia|data)\b', q))
        wants_time = bool(re.search(r'\b(?:hora|horas|horario)\b', q))
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
