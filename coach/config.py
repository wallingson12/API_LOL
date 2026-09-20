"""
config.py — Configurações do LoL Coach
"""

import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")

# Live Client Data API (local, durante a partida)
LIVE_API_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"

# LCU API (local, cliente do LoL — auth via lockfile)
LOCKFILE_PATH = r"C:\Riot Games\League of Legends\lockfile"

# Data Dragon (estático, baixado uma vez e cacheado)
DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON_ITEM_URL_TMPL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/pt_BR/item.json"
DDRAGON_CHAMP_URL_TMPL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/pt_BR/champion.json"
DDRAGON_CHAMP_DETAIL_URL_TMPL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/pt_BR/champion/{champ_id}.json"
DDRAGON_RUNES_URL_TMPL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/pt_BR/runesReforged.json"
ITEMS_FILE = os.path.join(_DATA_DIR, "items.json")
CHAMPIONS_FILE = os.path.join(_DATA_DIR, "champions.json")
ITENS_MAGO_FILE = os.path.join(_DATA_DIR, "itens_mago.json")
RUNES_FILE = os.path.join(_DATA_DIR, "runes.json")
USER_NOTICES_FILE = os.path.join(_DATA_DIR, "user_notices.json")

# Polling (API local — 0.5s reduz atraso sem sobrecarregar)
POLL_INTERVAL_SECONDS = 0.5
POLL_INTERVAL_MENU_SECONDS = 2

# Cooldown entre alertas repetidos do mesmo tipo (evita spam)
ALERT_COOLDOWN_SECONDS = 15
NUM_ADVANTAGE_MIN_DIFF = 2  # fala só com vantagem clara (ex.: 5 contra 3)
JUNGLE_LANE_LOOK_INTERVAL_SECONDS = 90   # olhar lanes / gank
JUNGLE_OBJECTIVE_REMINDER_INTERVAL_SECONDS = 120  # objetivo já no mapa

# Limiares de alerta
GOLD_ALERT_THRESHOLDS = [1000]
GOLD_RESET_MARGIN = 150
LEVEL_ALERTS = {6, 11, 16}
LANE_LEVEL_DANGER_GAP = 2
MY_DEATH_STREAK_COUNT = 2
MY_DEATH_STREAK_WINDOW_SECONDS = 300  # 5 minutos de gameTime
FEEDER_DEATH_COUNT = 2
FEEDER_WINDOW_SECONDS = 300  # 2 mortes do aliado nessa janela → rota feedando
FEEDER_ALERT_COOLDOWN_SECONDS = 180  # repete alerta da mesma rota após 3 min
RESPAWN_ALERT_COOLDOWN_SECONDS = 60

# Objetivos (Summoner's Rift — segundos de gameTime)
DRAGON_FIRST_SPAWN = 300          # 5:00
DRAGON_RESPAWN = 300              # elemental
ELDER_DRAGON_RESPAWN = 360        # 6:00 após alma
DRAGON_SOUL_COUNT = 4
HERALD_FIRST_SPAWN = 840          # 14:00 (após larvas do Void)
BARON_FIRST_SPAWN = 1200          # 20:00
BARON_RESPAWN = 360
BARON_SPAWN_ENDS_HERALD = 1200
OBJECTIVE_SPAWN_ALERT_SECONDS = 30
OBJECTIVE_WARD_SECONDS = 0        # desligado — só aviso de spawn (30s) + ping
VOIDGRUB_FIRST_SPAWN = 360        # 6:00
VOIDGRUB_RESPAWN = 240            # 4:00 após limpar o trio
VOIDGRUB_SECOND_WAVE_DEADLINE = 585  # 9:45 — 1ª leva precisa cair antes
VOIDGRUB_DESPAWN = 825            # 13:45 — camp some pro arauto
VOIDGRUB_WARD_SECONDS = 0         # desligado — evita poluição com larvas

# Wards (trinket amarelo)
YELLOW_WARD_DURATION_MIN = 90     # level médio baixo
YELLOW_WARD_DURATION_MAX = 120    # level médio ~18
WARD_EXPIRY_WARNING_SECONDS = 15  # avisa antes de sumir
WARD_PLACE_REMINDER_SECONDS = 240  # menos spam de visão
TRINKET_FULL_REMINDER_SECONDS = 60
TRINKET_ITEM_IDS = frozenset({3340})  # Warding Totem (amarelo)

# Recursos (HUD / recall)
MANA_LOW_RATIO = 0.22
HP_LOW_RATIO = 0.28
HP_CRITICAL_RATIO = 0.18
RESOURCE_ALERT_COOLDOWN_SECONDS = 90

# Lembrete de mapa (não-jungle) — só HUD escrito
MAP_REMINDER_INTERVAL_SECONDS = 120

# Voz — Antonio Natural (WinRT) com fallback para Maria Desktop (SAPI)
VOICE_BACKEND = "natural"
VOICE_ID = "pt-BR-AntonioNeural"
VOICE_NAME = "Microsoft Antonio (Natural) - Portuguese (Brazil)"
VOICE_RATE = 175
VOICE_PITCH = 1.1
VOICE_VOLUME = 1.0

# Alertas desligados
ENABLE_LANE_FEEDING_ALERTS = False
