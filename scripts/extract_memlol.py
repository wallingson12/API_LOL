"""
Extrai vídeos de habilidades do memlol.com para todos os campeões.

Exemplo: https://www.memlol.com/?champion=Yasuo&skill=Q
O <video> fica em /html/body/div/div/center/div[2]/video (#display).

Uso (na raiz do repo):
  python scripts/extract_memlol.py
  python scripts/extract_memlol.py --champion Yasuo
  python scripts/extract_memlol.py --no-download
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote, urljoin

import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAMPIONS_FILE = os.path.join(ROOT_DIR, "coach", "data", "champions.json")
OUTPUT_JSON = os.path.join(ROOT_DIR, "data", "memlol_abilities.json")
VIDEO_DIR = os.path.join(ROOT_DIR, "data", "memlol_videos")

BASE_URL = "https://www.memlol.com/"
PAGE_URL = "https://www.memlol.com/?champion={champion}&skill={skill}"
RIOT_CDN = (
    "https://lol.dyn.riotcdn.net/x/videos/champion-abilities/"
    "{key}/ability_{key}_{skill}1.{ext}"
)
SKILLS = ("Q", "W", "E", "R")

# memlol usa nome de tela, não o id do Data Dragon
MEMLOL_SLUGS = {
    "AurelionSol": "Aurelion Sol",
    "Belveth": "Bel'Veth",
    "Chogath": "Cho'Gath",
    "DrMundo": "Dr. Mundo",
    "JarvanIV": "Jarvan IV",
    "KSante": "K'Sante",
    "Kaisa": "Kai'Sa",
    "Khazix": "Kha'Zix",
    "KogMaw": "Kog'Maw",
    "LeeSin": "Lee Sin",
    "MasterYi": "Master Yi",
    "MissFortune": "Miss Fortune",
    "MonkeyKing": "Wukong",
    "RekSai": "Rek'Sai",
    "TahmKench": "Tahm Kench",
    "TwistedFate": "Twisted Fate",
    "Velkoz": "Vel'Koz",
    "XinZhao": "Xin Zhao",
}

_HEADERS = {
    "User-Agent": "API_LOL/1.0 (memlol ability extractor)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
}

_TAG_RE = re.compile(r"<[^>]+>")
_EXT_RE = re.compile(r"\.(webm|mp4)(?:\?|$)", re.I)


class _DisplayParser(HTMLParser):
    """Pega o <video> do #display (mesmo nó do XPath informado)."""

    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []
        self.answer = ""
        self.cooldown = ""
        self._in_video = False
        self._in_answer = 0
        self._in_cd = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ids = {k: v for k, v in attrs if v is not None}
        if tag == "video":
            self._in_video = True
            src = ids.get("src")
            if src:
                self.sources.append(src)
            return
        if tag == "source" and self._in_video:
            src = ids.get("src")
            if src:
                self.sources.append(src)
            return
        if tag == "div" and ids.get("id") == "answer":
            self._in_answer += 1
            return
        if tag == "div" and ids.get("id") == "cooldowns":
            self._in_cd += 1
            return
        if self._in_answer and tag == "div":
            self._in_answer += 1
        if self._in_cd and tag == "div":
            self._in_cd += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "video":
            self._in_video = False
        elif tag == "div":
            if self._in_answer:
                self._in_answer -= 1
            if self._in_cd:
                self._in_cd -= 1

    def handle_data(self, data: str) -> None:
        if self._in_answer:
            self.answer += data
        if self._in_cd:
            self.cooldown += data


def _load_profiles() -> dict[str, dict]:
    with open(CHAMPIONS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    by_id = {p["id"]: p for p in raw.values() if p.get("id")}
    if not by_id:
        raise RuntimeError(f"Nenhum campeão em {CHAMPIONS_FILE}")
    return by_id


def _load_champion_ids() -> list[str]:
    return sorted(_load_profiles())


def _padded_key(profile: dict) -> str | None:
    key = str(profile.get("key") or "").strip()
    if not key.isdigit():
        return None
    return key.zfill(4)


def _cdn_videos(key: str, skill: str) -> dict[str, str]:
    return {
        ext: RIOT_CDN.format(key=key, skill=skill, ext=ext)
        for ext in ("webm", "mp4")
    }


def _parse_page(html: str) -> dict:
    parser = _DisplayParser()
    parser.feed(html)
    videos: dict[str, str] = {}
    for src in parser.sources:
        abs_url = urljoin(BASE_URL, src.strip())
        m = _EXT_RE.search(abs_url)
        if m:
            videos[m.group(1).lower()] = abs_url
        elif abs_url and "fallback" not in videos:
            videos["fallback"] = abs_url
    return {
        "label": _TAG_RE.sub("", parser.answer).strip(),
        "cooldown": parser.cooldown.strip(),
        "videos": videos,
    }


def _page_url(slug: str, skill: str) -> str:
    return PAGE_URL.format(champion=quote(slug, safe=""), skill=skill)


def _fetch_page(
    session: requests.Session,
    champion: str,
    skill: str,
    key: str | None = None,
) -> dict:
    slugs = [champion]
    alias = MEMLOL_SLUGS.get(champion)
    if alias and alias not in slugs:
        slugs.insert(0, alias)

    last_error: Exception | None = None
    for slug in slugs:
        url = _page_url(slug, skill)
        try:
            r = session.get(url, headers=_HEADERS, timeout=20)
            r.raise_for_status()
            parsed = _parse_page(r.text)
            parsed["page"] = url
            parsed["ok"] = bool(parsed["videos"])
            if parsed["ok"]:
                return parsed
        except requests.RequestException as e:
            last_error = e

    if key:
        return {
            "label": f"{champion} {skill}",
            "cooldown": "",
            "videos": _cdn_videos(key, skill),
            "page": _page_url(slugs[0], skill),
            "ok": True,
            "via": "riot_cdn",
        }

    if last_error:
        raise last_error
    return {
        "label": "",
        "cooldown": "",
        "videos": {},
        "page": _page_url(slugs[0], skill),
        "ok": False,
    }


def _video_filename(champion: str, skill: str, url: str) -> str:
    ext = "webm"
    m = _EXT_RE.search(url)
    if m:
        ext = m.group(1).lower()
    return f"{champion}_{skill}.{ext}"


def _download_video(session: requests.Session, url: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with session.get(url, headers=_HEADERS, timeout=60, stream=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)


def _prefer_video_url(videos: dict[str, str]) -> str | None:
    return videos.get("webm") or videos.get("mp4") or videos.get("fallback")


def _ensure_video_file(session: requests.Session, row: dict, champion: str, skill: str, force: bool) -> str | None:
    url = _prefer_video_url(row.get("videos") or {})
    if not url:
        return None
    dest = os.path.join(VIDEO_DIR, _video_filename(champion, skill, url))
    if force or not os.path.exists(dest) or os.path.getsize(dest) == 0:
        _download_video(session, url, dest)
    row["file"] = dest
    return dest


def extract(
    champions: list[str],
    skills: tuple[str, ...] = SKILLS,
    delay: float = 0.2,
    download: bool = True,
    force: bool = False,
) -> dict:
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    payload: dict = {
        "source": BASE_URL,
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "skills": list(skills),
        "entries": {},
    }
    if os.path.exists(OUTPUT_JSON) and not force:
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old.get("entries"), dict):
                payload["entries"] = old["entries"]
        except Exception:
            pass

    profiles = _load_profiles()
    session = requests.Session()
    ok = skipped = failed = 0
    total = len(champions) * len(skills)
    n = 0

    for champ in champions:
        champ_block = payload["entries"].setdefault(champ, {})
        key = _padded_key(profiles.get(champ) or {})
        for skill in skills:
            n += 1
            existing = champ_block.get(skill) if isinstance(champ_block.get(skill), dict) else None
            have_urls = bool(existing and existing.get("ok") and existing.get("videos"))

            try:
                if have_urls and not force:
                    row = existing
                else:
                    row = _fetch_page(session, champ, skill, key=key)
                    champ_block[skill] = row

                if row.get("ok"):
                    if download:
                        dest = _ensure_video_file(session, row, champ, skill, force)
                        ok += 1
                        print(f"  [{n}/{total}] {champ} {skill}  {dest or ''}")
                    else:
                        skipped += 1
                        print(f"  [{n}/{total}] skip download {champ} {skill}")
                else:
                    failed += 1
                    print(f"  [{n}/{total}] sem vídeo {champ} {skill}")
            except requests.RequestException as e:
                failed += 1
                champ_block[skill] = {
                    "page": PAGE_URL.format(champion=champ, skill=skill),
                    "ok": False,
                    "error": str(e),
                    "videos": {},
                }
                print(f"  [{n}/{total}] falhou {champ} {skill}: {e}")

            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            if delay > 0:
                time.sleep(delay)

    payload["extracted_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nOK {ok}  skip {skipped}  falha {failed}")
    print(f"JSON: {OUTPUT_JSON}")
    if download:
        print(f"Vídeos: {VIDEO_DIR}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrai vídeos de habilidades do memlol.com.")
    parser.add_argument("--champion", help="Só este campeão (id Data Dragon, ex: Yasuo).")
    parser.add_argument("--retry-failed", action="store_true", help="Só campeões que falharam no JSON.")
    parser.add_argument("--skills", default="Q,W,E,R", help="Skills separados por vírgula. Default: Q,W,E,R")
    parser.add_argument("--delay", type=float, default=0.2, help="Pausa entre páginas, em segundos.")
    parser.add_argument("--no-download", action="store_true", help="Só atualiza o JSON, sem baixar vídeo.")
    parser.add_argument("--force", action="store_true", help="Refaz scrape e download mesmo se já existir.")
    parser.add_argument("--limit", type=int, default=0, help="Limita quantos campeões (0 = todos).")
    args = parser.parse_args()

    skills = tuple(s.strip().upper() for s in args.skills.split(",") if s.strip())
    if not skills:
        print("Nenhuma skill.", file=sys.stderr)
        return 1

    if args.champion:
        champions = [args.champion]
    elif args.retry_failed and os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            old = json.load(f)
        champions = sorted(
            champ
            for champ, skills in (old.get("entries") or {}).items()
            if any(not (row or {}).get("ok") for row in skills.values())
        )
        if not champions:
            print("Nenhuma falha no JSON.")
            return 0
    else:
        champions = _load_champion_ids()
        if args.limit > 0:
            champions = champions[: args.limit]

    print(f"{len(champions)} campeão(ões), skills {','.join(skills)}\n")
    extract(
        champions,
        skills=skills,
        delay=args.delay,
        download=not args.no_download,
        force=args.force,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
