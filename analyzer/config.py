import os
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "data"
_DATA.mkdir(exist_ok=True)

load_dotenv(_ROOT / ".env")

# ─────────────────────────────────────────
# CONFIGURAÇÃO — edite aqui
# ─────────────────────────────────────────
API_KEY      = (os.getenv("API_KEY", "") or "").strip().strip('"').strip("'")
RIOT_ID      = "CadêOWally#wall"
REGION       = "americas"       # para contas BR
PLATFORM     = "br1"            # plataforma BR
QTD_PARTIDAS = 100              # quantas partidas analisar (max 100)
OUTPUT_DIR   = str(_DATA)
MAP_IMAGE_PATH = str(_DATA) + "\\mapa.webp"
# ─────────────────────────────────────────

if not API_KEY:
    raise SystemExit("❌ API_KEY não encontrada. Crie um arquivo .env com API_KEY=RGAPI-...")

HEADERS = {"X-Riot-Token": API_KEY}

FILAS = {
    "1": ("Ranked Solo/Duo", 420),
    "2": ("Ranked Flex",     440),
    "3": ("ARAM",            450),
    "4": ("Normal Draft",    400),
    "5": ("Normal Blind",    430),
    "6": ("Todas as filas",  None),
}
