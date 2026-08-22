# API_LOL

Dois projetos independentes na mesma pasta:

| Pasta | O que faz | Como rodar |
|---|---|---|
| `analyzer/` | Analisa partidas passadas via Riot API (CSV, heatmap) | `python analyzer/main.py` |
| `coach/` | Coach de voz em tempo real (Live Client + LCU) | `python coach/main.py` |

## Instalação

```bash
pip install -r requirements.txt
```

## Configuração

Crie `.env` na raiz com a chave da Riot (só o analisador precisa):

```
API_KEY=RGAPI-xxxx-xxxx-xxxx
```

Edite `analyzer/config.py` para `RIOT_ID`, filas e quantidade de partidas.

Para o heatmap, coloque `mapa.webp` em `data/`.

## Estrutura

```
API_LOL/
├── analyzer/          → analisador de partidas (Riot API remota)
├── coach/             → coach de voz (API local durante a partida)
│   ├── api/           → Live Client + LCU
│   ├── analysis/      → alertas táticos
│   ├── data/          → cache Data Dragon (itens, campeões)
│   ├── game/          → detecção de eventos
│   └── voice/         → TTS em PT-BR
├── data/              → CSVs e mapas gerados pelo analisador
├── assets/            → ícones e recursos estáticos
├── docs/              → notas e documentação extra
├── .env               → API_KEY (não commitar)
└── requirements.txt
```

## Arquivos gerados (analisador)

Saem em `data/`:

| Arquivo | Conteúdo |
|---|---|
| `partidas_pessoal.csv` | Seus dados por partida |
| `partidas_completo.csv` | Dados dos 10 jogadores |
| `eventos_mortes.csv` | Kills com coordenadas X/Y |
| `mapa_calor_mortes.png` | Heatmap de mortes |

## Documentação Riot

https://developer.riotgames.com/
