# Sexta-Feira

Assistente pessoal de voz para Linux (Wayland/X11), com IA local por padrão (Ollama) e opção de API (OpenRouter).

## O que ela faz

- **Ativação por voz**: só responde quando você chama "Sexta-Feira" (configurável); depois disso fica em conversa aberta e adormece após ~20s sem interação. O nome é reconhecido com um modelo Whisper `tiny` (resposta rápida) e o comando é transcrito com o modelo principal
- **Interrupção**: `Ctrl+X` interrompe o que ela está falando/pensando na hora; `Ctrl+E` fecha o orb
- **Voz**: transcrição local (faster-whisper), fala (edge-tts) em streaming (frase por frase), detecção de fala por VAD (energia ou Silero opcional)
- **Aquecimento**: o modelo do Ollama é pré-carregado no boot (sem espera na primeira pergunta)
- **Comandos instantâneos** (sem LLM): horas/data, clima (wttr.in), abrir navegador/sites/pastas/apps, pesquisar na web, organizar área de trabalho, volume, música (playerctl), timers, captura de tela, bloquear tela, notícias (RSS)
- **Memória**: histórico da conversa durante a sessão; anota fatos que você disser ("lembre que...", "meu nome é...")
- **Interface**: orb flutuante que reage ao volume da sua voz, muda de cor por estado (azul=escutando, laranja=pensando, verde=falando) e fica apagada fora da sessão

## Requisitos

- Linux (testado no niri/Wayland; funciona em outros com ajustes)
- Python 3.10+
- Ollama com um modelo (`ollama pull qwen2.5:3b`)
- `mpv` ou `ffplay` para reproduzir a voz
- Opcional: `playerctl` (controle de música), `notify-send` (timers), `grim`/`scrot`/`flameshot` (captura)

## Instalação

```bash
git clone https://github.com/Rafael-Behling/Assistente-pessoal.git
cd Assistente-pessoal
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
ollama pull qwen2.5:3b
```

### Atalho global (Ctrl+E fecha o orb)

```bash
sudo cp 66-sexta-feira-input.rules /etc/udev/rules.d/
sudo usermod -aG input $USER   # depois faça logout/login
sudo udevadm control --reload && sudo udevadm trigger
```

## Uso

```bash
python main.py
```

Na primeira vez abre o menu para escolher a voz; depois o orb aparece no canto da tela. Fale "Sexta-Feira..." seguido do comando.

Exemplos: "que horas são", "como está o tempo", "abre o youtube", "pesquisar receita de bolo", "me avisa em 10 minutos", "próxima música", "lembre que eu gosto de pizza", "o que você sabe sobre mim".

### Iniciar junto com o sistema

```bash
cp assets/sexta-feira.desktop ~/.config/autostart/
```
(Ajuste os caminhos dentro do arquivo para o seu diretório.)

## Configuração

Edite `config.json` (ou pelo menu gráfico ao abrir sem voz) — veja `config.example.json`:

| Chave | Descrição |
|---|---|
| `voice` | Voz do edge-tts (ex: `pt-BR-FranciscaNeural`) |
| `activation.mode` | `wake_word` (só responde ao nome) ou `always_on` |
| `activation.wake_words` | Variações aceitas do nome |
| `activation.session_timeout_s` | Segundos de silêncio até adormecer |
| `vad.engine` | `energy` (padrão) ou `silero` (requer `pip install silero-vad`) |
| `stt.model` | Modelo Whisper (`tiny`, `base`, `small`...) |
| `llm.mode` | `local` (Ollama) ou `api` (OpenRouter, precisa `api_key`) |
| `weather.location` | Cidade para o clima (vazio = por IP) |

## Estrutura

```
main.py            entrada (lock de instância única, escolhe orb/menu)
core/vad.py        captura de microfone + detecção de fala (energia/Silero)
core/stt.py        transcrição (faster-whisper)
core/brain.py      orquestra tudo: wake word, sessão, comandos, LLM, memória
core/commands.py   comandos locais por regex
core/memory.py     histórico e fatos (data/*.jsonl, data/fatos.json)
core/llm/          provedores (Ollama, OpenRouter)
ui/orb.py          orbe visual (PyQt6)
ui/menu.py         seleção de voz
```
