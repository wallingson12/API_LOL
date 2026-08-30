# Coach — catálogo de alertas

Instalação e visão do repo: [`README.md`](../README.md) na raiz.

`python main.py` sobe a UI, o coach e o rastreador (`vision/`). Deixe rodando antes da fila.

---

## Visão geral

| Fonte | Módulo | O que faz |
|---|---|---|
| Eventos da API | `game/events.py` | Kills, torres, gold, respawn |
| Alertas táticos | `analysis/coaching_alerts.py` | Bot, jg, 3 mortos |
| Objetivos | `analysis/objective_spawns.py` | Timers de drag, larvas, arauto, barão |
| Suas mortes | `analysis/my_deaths.py` | 2 mortes em 5 min |
| Torres por rota | `analysis/tower_lane.py` | Primeira torre na lane |
| Lane level | `analysis/lane_level.py` | Oponente +2 níveis |
| Frases | `voice/narrator.py` | Texto falado em PT-BR |
| Cooldown | `voice/voice.py` | Evita repetir o mesmo alerta |

**Cooldown padrão:** `ALERT_COOLDOWN_SECONDS = 15` — mesma `alert_key` não repete antes desse intervalo (exceto onde indicado).

**Polling:** a cada `0.5s` durante a partida.

---

## Alertas — pré-jogo

| Frase | Regra | Cooldown |
|---|---|---|
| *"Champ select iniciado."* | Fase LCU = ChampSelect e picks ainda indisponíveis | 300s |
| *"Seu time: X. Inimigos: Y."* | Champ select com campeões identificados; só repete se a composição mudar | 120s |

---

## Alertas — início da partida

| Frase | Regra | Cooldown |
|---|---|---|
| *"Coach de voz pronto."* | Teste de TTS ao iniciar o programa | — |
| *"Coach conectado. Boa sorte."* | Live Client detecta partida ativa | 1× por partida |

---

## Alertas — eventos (`narrate_event`)

Detectados por mudança de estado ou feed da API. **Eventos já ocorridos antes de conectar são ignorados** (bootstrap do feed).

### Ouro

| Frase | Regra | Repete? |
|---|---|---|
| *"Mil de ouro, volte para base."* | Seu gold cruza **1000** no bolso | 1× até cair abaixo de **850** (`GOLD_RESET_MARGIN`) |

### Torres e inibidores

| Frase | Regra |
|---|---|
| *"Você destruiu {T1/T2/T3 do lane (time)}."* | Você deu last hit na estrutura inimiga |
| *"Inimigo destruiu {estrutura}."* | Jogador inimigo destruiu estrutura (sua ou deles, conforme o evento) |
| *"Minions inimigos destruíram {estrutura}. Sugiro defender a rota {lane}."* | Minions inimigos destruíram **sua** torre/inibidor |
| *"Seus minions destruíram {estrutura}."* | Seus minions destruíram estrutura inimiga |

Formato da estrutura: `T1/T2/T3 do top|mid|bot (azul|vermelho)`.

### Respawn inimigo

| Frase | Regra |
|---|---|
| *"{Role} inimigo voltou."* | Inimigo renasce; role = ADC, Suporte, Top, Mid ou Jungler quando a API informa |
| *"Inimigo voltou."* | Inimigo renasce sem role identificada |

Não fala respawn de aliados nem o seu.

---

## Alertas — táticos (`narrate_alert`)

### Bot lane (vantagem numérica)

| Frase | Regra |
|---|---|
| *"Bot: dois contra um."* | Inimigo ADC **ou** Suporte morre; **seu ADC e Suporte estão vivos**; resta **1** inimigo vivo no bot |
| *"Bot: dois contra {N}."* | Mesma condição, se a API reportar mais de 1 inimigo vivo no bot (caso raro) |

**Não fala:** "ADC exposto", "Suporte exposto", "bot wipeado".  
**Não fala** *"Bot: dois contra zero"* — wipe completo (0 inimigos no bot) não dispara alerta (só quando resta ≥ 1).

Prioridade: se **3+ inimigos** estão mortos no mapa, o alerta de bot **não** dispara naquele abate (vale o alerta de 3 mortos).

### Três inimigos mortos

| Frase | Regra |
|---|---|
| *"Três inimigos mortos. {Objetivo} disponível."* | **3 ou mais** inimigos mortos simultaneamente; nomeia objetivos **no mapa agora** (drag, ancião, larvas, arauto, barão) |
| *"Três inimigos mortos. Sem objetivo neutro no momento, pressione torres."* | 3+ mortos e nenhum objetivo neutro disponível |

Objetivos considerados: Dragão, Dragão Ancião, Larvas do Void, Arauto (antes de 20:00), Barão.

### Jungler inimigo

| Frase | Regra |
|---|---|
| *"Jungler inimigo morto. Boa janela de gank ou invade."* | Inimigo com role jungler (posição ou Smite) morre; **não** quando já há 3+ inimigos mortos no mesmo tick |

### Suas mortes (tilt)

| Frase | Regra |
|---|---|
| *"Fique calmo e foque no farm."* | Você morre **2 vezes** dentro de **5 minutos** de `gameTime` (`MY_DEATH_STREAK_WINDOW_SECONDS = 300`); conta qualquer killer; após falar, reinicia a contagem |

### Torre antes do inimigo na rota

| Frase | Regra |
|---|---|
| *"Torre na {top\|mid\|bot} antes do inimigo. Olhe as sides."* | Seu time destrói torre **inimiga** na lane **antes** de perder qualquer torre sua na mesma lane; **1× por lane** por partida |

### Par da lane (+ níveis)

| Frase | Regra |
|---|---|
| *"Cuidado: {Role} inimigo está {N} níveis acima. Virando monstro."* | Oponente da **sua role** está **≥ 2 níveis** acima (`LANE_LEVEL_DANGER_GAP`); fala **1×** até a vantagem cair abaixo de 2 |

---

## Alertas — objetivos (`objective_spawns.py`)

Timers baseados em `gameTime` + kills de drag/baron/herald/larvas na API. Após **4º drag elemental** do mesmo time → próximo spawn é **Dragão Ancião** (+6:00).

### Ward (visão antecipada)

| Frase | Quando | Antecedência |
|---|---|---|
| *"Coloque visão no dragão. Surge em {N} segundos."* | Drag elemental | **90s** antes (`OBJECTIVE_WARD_SECONDS`) |
| *"Coloque visão no Dragão Ancião. Surge em {N} segundos."* | Fase ancião | **90s** |
| *"Coloque visão no arauto. Surge em {N} segundos."* | Arauto | **90s** |
| *"Coloque visão no barão. Surge em {N} segundos."* | Barão | **90s** |
| *"Coloque visão nas larvas do Void. Surgem em {N} segundos."* | Larvas | **45s** (`VOIDGRUB_WARD_SECONDS`) |

Cada objetivo avisa ward **1×** por ciclo de spawn.

### Spawn iminente

| Frase | Quando | Antecedência |
|---|---|---|
| *"Dragão vai surgir em {N} segundos."* | Drag elemental | **≤ 60s** |
| *"Dragão Ancião vai surgir em {N} segundos."* | Ancião | **≤ 60s** |
| *"Arauto vai surgir em {N} segundos."* | Arauto (some após 20:00) | **≤ 60s** |
| *"Barão vai surgir em {N} segundos."* | Barão | **≤ 60s** |
| *"Larvas do Void vão surgir em {N} segundos."* | Larvas (1ª leva 6:00; 2ª +4:00 se limpar antes de 9:45; camp some 13:45) | **≤ 60s** |

### Timers padrão (1º spawn)

| Objetivo | gameTime |
|---|---|
| Larvas do Void | 6:00 |
| Dragão | 5:00 |
| Arauto | 14:00 |
| Barão | 20:00 |

Respawn drag elemental: **5:00** · Ancião: **6:00** · Barão: **6:00** · Larvas 2ª leva: **4:00** após limpar trio.

---

## Alertas — lembrete fixo

| Frase | Regra | Cooldown |
|---|---|---|
| *"Olhe o mapa."* | A cada **1:30** (`MAP_REMINDER_INTERVAL_SECONDS = 90`) durante a partida | 90s |

---

## O que **não** fala (silenciado de propósito)

| Evento detectado | Motivo |
|---|---|
| Abates no feed (*"X abateu Y"*) | Removido — só alertas táticos derivados |
| Sua morte / morte de aliado (evento isolado) | Sem narração; tilt só via regra de 2 mortes em 5 min |
| First blood | Filtrado (redundante com kill) |
| Compra de item | Filtrado |
| Level up (6, 11, 16 ou outros) | Detectado, mas **sem frase** no narrador atual |
| Dragão / Barão / Arauto / Larvas **abatidos** | Evento existe; **sem frase** |
| Fim de jogo (Vitória/Derrota) | Evento existe; **sem frase** |
| Respawn seu ou de aliado | Ignorado |

---

## Limitações da API

O coach **não** sabe (e portanto **não** alerta):

- Posição no mapa, waves, rotações
- Cooldown de Flash / Teleporte inimigo
- Visão real (wards colocadas)
- Atakhan (removido do jogo)

Tudo depende do que a **Live Client Data API** expõe em `127.0.0.1:2999`.

---

## Configuração (`config.py`)

| Constante | Padrão | Efeito |
|---|---|---|
| `GOLD_ALERT_THRESHOLDS` | `[1000]` | Marco de ouro para base |
| `GOLD_RESET_MARGIN` | `150` | Re-alerta gold após cair ~850 |
| `MAP_REMINDER_INTERVAL_SECONDS` | `90` | Intervalo "Olhe o mapa" |
| `MY_DEATH_STREAK_COUNT` | `2` | Mortes suas para pedir calma |
| `MY_DEATH_STREAK_WINDOW_SECONDS` | `300` | Janela (5 min gameTime) |
| `LANE_LEVEL_DANGER_GAP` | `2` | Níveis acima do oponente de lane |
| `ALERT_COOLDOWN_SECONDS` | `15` | Cooldown global por `alert_key` |
| `OBJECTIVE_WARD_SECONDS` | `90` | Ward drag/arauto/barão/ancião |
| `VOIDGRUB_WARD_SECONDS` | `45` | Ward larvas |
| `OBJECTIVE_SPAWN_ALERT_SECONDS` | `60` | Alerta spawn iminente |
| `POLL_INTERVAL_SECONDS` | `0.5` | Frequência de leitura da API |
| `VOICE_RATE` / `VOICE_VOLUME` | `175` / `1.0` | Velocidade e volume TTS (Windows) |

---

## Estrutura

```
coach/
├── engine.py               liga voz, alertas e vision
├── config.py
├── api/                    Live Client + LCU
├── analysis/               regras
├── alerts/                 prioridade / canais
├── vision/                 rastreador (print + modelo)
├── game/events.py
├── voice/
├── ui/
└── data/                   cache Data Dragon
```
