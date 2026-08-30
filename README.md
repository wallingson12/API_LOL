# API_LOL

Coach em tempo real, rastreador visual de campeão e analisador de histórico — um repo, um ponto de entrada.

```bash
python main.py
```

A UI sobe o **coach**. O **rastreador** liga junto (print da janela do LoL → MobileNet → caixa no boneco). O **analisador** de partidas fica na aba da mesma interface.

## O que tem aqui

| Parte | Pasta | Função |
|---|---|---|
| Coach | `coach/` | Live Client + LCU: voz, HUD, avisos, itens, objetivos |
| Rastreador | `coach/vision/` | Identifica o campeão na tela e desenha a caixa |
| Analisador | `analyzer/` | Histórico Riot API (CSVs, heatmap) |
| Scripts | `scripts/` | Extrair clipes, treinar o modelo, baixar ícones |

## Instalação

Python 3.11+ (Windows). Na raiz:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

O modelo fica em `data/ml_ability/mobilenet.keras`. Sem esse arquivo o coach sobe e o rastreador registra que está indisponível.

## Uso

1. LoL em **Janela** (com borda). Tela cheia / sem bordas o Windows não deixa overlay por cima do DirectX.
2. `python main.py`
3. Inicia o coach na UI. O rastreador sobe na mesma hora.
4. Câmera no dummy (Y) no treino ajuda a caixa a ficar no boneco.

O print **não é gravado em disco**. Só existe na RAM, o modelo lê e descarta. O nome visto vai para `AppState` (`vision_champion`, `vision_confidence`).

## Configuração

Crie `.env` na raiz (veja `.env.example`). Só o analisador precisa da chave:

```
API_KEY=RGAPI-xxxx-xxxx-xxxx
```

Riot ID, filas e quantidade de partidas: `analyzer/config.py`.  
Constantes do coach (cooldowns, timers): `coach/config.py`.

## Rastreador e modelo

O MobileNet **classifica** o print (quem é). A posição da caixa usa a barra de vida; se não achar, o ponto da câmera travada. Não é um detector tipo YOLO.

Treino (depois de baixar os clipes):

```bash
python scripts/extract_memlol.py
python scripts/train_ability_ml.py
```

Clipes em `data/memlol_videos/` (gitignored). Índice em `data/memlol_abilities.json`.

Ícones Data Dragon:

```bash
python scripts/download_icons.py
```

## Estrutura

```
API_LOL/
├── main.py                 ponto de entrada (UI + coach + rastreador)
├── requirements.txt
├── .env.example
├── coach/                  runtime do coach
│   ├── engine.py           liga voz, alertas e vision.start_tracker()
│   ├── app_state.py        estado compartilhado com a UI
│   ├── api/                Live Client + LCU
│   ├── analysis/           regras táticas
│   ├── alerts/             prioridade e canais (voz / HUD)
│   ├── vision/             rastreador (detect.py)
│   ├── game/               eventos da partida
│   ├── voice/              TTS PT-BR
│   ├── ui/                 desktop
│   └── data/               cache Data Dragon (champions, items)
├── analyzer/               histórico Riot API
├── scripts/                ferramentas (não rodam com o coach)
│   ├── extract_memlol.py
│   ├── train_ability_ml.py
│   └── download_icons.py
├── data/                   gerados (vídeos, modelo, CSVs)
└── assets/                 ícones e perfis
```

`coach/data/` = dados oficiais em cache.  
`data/` = artefatos gerados (treino, análise). Não misturar.

## Analisador

Saídas em `data/`:

| Arquivo | Conteúdo |
|---|---|
| `partidas_pessoal.csv` | Suas linhas por partida |
| `partidas_completo.csv` | Os 10 jogadores |
| `eventos_mortes.csv` | Kills com X/Y |
| `mapa_calor_mortes.png` | Heatmap |

Para o heatmap, coloque `mapa.webp` em `data/`.

## Alertas do coach

Lista completa das frases e regras: [`coach/README.md`](coach/README.md).

O coach **não** vê posição no mapa, CD de Flash inimigo nem wards reais. Tudo que fala vem da Live Client (`127.0.0.1:2999`) ou do rastreador na tela.

## Documentação Riot

https://developer.riotgames.com/
