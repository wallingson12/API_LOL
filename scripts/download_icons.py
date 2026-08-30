import argparse
import io
import json
import os
import sys

import requests
from PIL import Image

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "assets", "champion_icons")
PROFILES_FILE = os.path.join(ROOT_DIR, "assets", "champion_profiles.json")
DETAILS_DIR = os.path.join(ROOT_DIR, "assets", "champion_details")

DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON_CHAMP_URL_TMPL = "q"
DDRAGON_CHAMP_DETAIL_URL_TMPL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/pt_BR/champion/{champ_id}.json"
DDRAGON_IMG_URL_TMPL = "https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{filename}"

_HEADERS = {"User-Agent": "API_LOL/1.0 (Data Dragon icon downloader)"}


def _get(url: str) -> requests.Response:
    r = requests.get(url, headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return r


def _fetch_latest_version() -> str:
    return _get(DDRAGON_VERSIONS_URL).json()[0]


def _fetch_champions(version: str) -> dict:
    url = DDRAGON_CHAMP_URL_TMPL.format(version=version)
    return _get(url).json()["data"]


def _save_icon(content: bytes, dest: str) -> None:
    img = Image.open(io.BytesIO(content)).convert("RGB")
    img.save(dest, "JPEG", quality=92)


def _build_profile(champ: dict) -> dict:
    """Campos úteis do champion.json (lista). tags = tipo/classe (Fighter, Mage...)."""
    return {
        "id": champ["id"],
        "key": champ["key"],
        "name": champ["name"],
        "title": champ.get("title", ""),
        "tags": champ.get("tags", []),
        "partype": champ.get("partype", ""),
        "info": champ.get("info", {}),
        "stats": champ.get("stats", {}),
        "blurb": champ.get("blurb", ""),
        "image": champ.get("image", {}).get("full", ""),
    }


def save_profiles(version: str, champions: dict) -> None:
    os.makedirs(os.path.dirname(PROFILES_FILE), exist_ok=True)
    payload = {
        "version": version,
        "champions": {
            str(champ["key"]): _build_profile(champ)
            for champ in champions.values()
        },
    }
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Perfis salvos: {PROFILES_FILE}")


def download_details(version: str, champions: dict, force: bool = False) -> tuple[int, int, int]:
    os.makedirs(DETAILS_DIR, exist_ok=True)
    ok = skipped = failed = 0

    for champ in champions.values():
        champ_id = champ["id"]
        dest = os.path.join(DETAILS_DIR, f"{champ_id}.json")

        if os.path.exists(dest) and not force:
            skipped += 1
            continue

        url = DDRAGON_CHAMP_DETAIL_URL_TMPL.format(version=version, champ_id=champ_id)
        try:
            detail = _get(url).json()["data"][champ_id]
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(detail, f, ensure_ascii=False, indent=2)
            ok += 1
            print(f"  ✓ detalhe {champ_id}")
        except Exception as e:
            failed += 1
            print(f"  ✗ detalhe {champ_id}: {e}")

    return ok, skipped, failed


def download_icons(force: bool = False, details: bool = False) -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    version = _fetch_latest_version()
    champions = _fetch_champions(version)
    print(f"Patch Data Dragon: {version}")
    print(f"Destino ícones: {OUTPUT_DIR}\n")

    save_profiles(version, champions)

    ok = skipped = failed = 0

    for champ in champions.values():
        champ_id = champ["id"]
        filename = champ["image"]["full"]
        dest = os.path.join(OUTPUT_DIR, f"{champ_id}.jpg")

        if os.path.exists(dest) and not force:
            skipped += 1
            continue

        url = DDRAGON_IMG_URL_TMPL.format(version=version, filename=filename)
        try:
            r = _get(url)
            _save_icon(r.content, dest)
            ok += 1
            print(f"  ✓ {champ_id}")
        except Exception as e:
            failed += 1
            print(f"  ✗ {champ_id}: {e}")

    print(f"\nÍcones: {ok} baixados, {skipped} já existiam, {failed} falharam.")

    if details:
        print(f"\nBaixando JSON completo por campeão em {DETAILS_DIR}...")
        d_ok, d_skip, d_fail = download_details(version, champions, force=force)
        print(f"Detalhes: {d_ok} baixados, {d_skip} já existiam, {d_fail} falharam.")
        failed += d_fail

    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Baixa ícones de campeões do Data Dragon.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Baixa de novo mesmo se o arquivo já existir.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Baixa também o JSON completo de cada campeão (habilidades, passiva, lore, dicas).",
    )
    args = parser.parse_args()

    try:
        return download_icons(force=args.force, details=args.details)
    except requests.RequestException as e:
        print(f"Erro ao acessar Data Dragon: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
