"""
item_data.py — Cache slim de itens (items.json) via Data Dragon
"""

import json
import os
import re
import requests
from config import DDRAGON_VERSIONS_URL, DDRAGON_ITEM_URL_TMPL, ITEMS_FILE

_cache = None  # {item_id_str: {"name":..., "classificacao":..., "efeitos":[...]}}

_EFEITO_CURA = "cura"
_EFEITO_ESCUDO = "escudo"
_EFEITO_CORTA_CURA = "corta_cura"
_EFEITO_VAMPIRISMO = "vampirismo"
_EFEITO_RM = "resistencia_magica"


def _fetch_latest_version() -> str:
    r = requests.get(DDRAGON_VERSIONS_URL, timeout=5)
    r.raise_for_status()
    return r.json()[0]


def _classificar_botas(tags_set: set, stats: dict) -> str:
    """Foco específico da bota (não só 'botas')."""
    armor = float(stats.get("FlatArmorMod") or 0)
    mr = float(stats.get("FlatSpellBlockMod") or 0)
    aspd = float(stats.get("PercentAttackSpeedMod") or 0)

    if "Tenacity" in tags_set or (mr > 0 and "SpellBlock" in tags_set):
        return "botas: tenacidade"
    if "MagicPenetration" in tags_set:
        return "botas: penetração mágica"
    if "Armor" in tags_set or armor > 0:
        return "botas: armadura"
    if "AttackSpeed" in tags_set or aspd > 0:
        return "botas: velocidade de ataque"
    if "CooldownReduction" in tags_set or "AbilityHaste" in tags_set:
        return "botas: aceleração de habilidade"
    if "LifeSteal" in tags_set or "SpellVamp" in tags_set:
        return "botas: roubo de vida"
    return "botas: movimento"


def _foco_secundario(tags_set: set, stats: dict) -> str:
    """Quando não há AP/AD/armadura/RM/vida: diz exatamente o que o item entrega."""
    crit = float(stats.get("FlatCritChanceMod") or 0) * 100
    aspd = float(stats.get("PercentAttackSpeedMod") or 0) * 100
    ms_flat = float(stats.get("FlatMovementSpeedMod") or 0)
    ms_pct = float(stats.get("PercentMovementSpeedMod") or 0) * 100
    mana = float(stats.get("FlatMPPoolMod") or 0) / 20.0
    lifesteal = float(stats.get("PercentLifeStealMod") or 0) * 100

    scores: dict[str, float] = {}

    if crit or "CriticalStrike" in tags_set:
        scores["chance crítica"] = crit or 12
    if aspd or "AttackSpeed" in tags_set:
        scores["velocidade de ataque"] = aspd or 12
    if mana or "Mana" in tags_set:
        scores["mana"] = mana or 12
    if "ManaRegen" in tags_set and "Mana" not in tags_set:
        scores["regeneração de mana"] = 12
    if "HealthRegen" in tags_set:
        scores["regeneração de vida"] = 10
    if lifesteal or "LifeSteal" in tags_set or "SpellVamp" in tags_set:
        scores["roubo de vida"] = lifesteal or 12
    if "MagicPenetration" in tags_set:
        scores["penetração mágica"] = 15
    if "ArmorPenetration" in tags_set:
        scores["penetração de armadura"] = 15
    if "CooldownReduction" in tags_set or "AbilityHaste" in tags_set:
        scores["aceleração de habilidade"] = 12
    if "OnHit" in tags_set:
        scores["dano ao acertar"] = 14
    if ms_flat or ms_pct or "NonbootsMovement" in tags_set:
        scores["velocidade de movimento"] = (ms_flat + ms_pct) or 10
    if "Tenacity" in tags_set:
        scores["tenacidade"] = 14
    if "Vision" in tags_set or "Stealth" in tags_set:
        scores["visão"] = 12
    if "Slow" in tags_set:
        scores["controle de movimento"] = 10
    if "Active" in tags_set or "Aura" in tags_set:
        scores.setdefault("efeito ativo", 8)

    if not scores:
        return "outros"
    return max(scores, key=scores.get)


def classificar_item(tags: list | None, stats: dict | None) -> str:
    """Classifica pelo foco do item (papel no build), não pelo maior número bruto."""
    tags_set = set(tags or [])
    stats = stats or {}

    if "Trinket" in tags_set:
        return "visão"
    if "Consumable" in tags_set:
        return "consumível"
    if "Boots" in tags_set:
        return _classificar_botas(tags_set, stats)
    if "GoldPer" in tags_set:
        return "suporte"
    if "Jungle" in tags_set and "Lane" not in tags_set:
        return "selva"

    ap = float(stats.get("FlatMagicDamageMod") or 0)
    ad = float(stats.get("FlatPhysicalDamageMod") or 0)
    armor = float(stats.get("FlatArmorMod") or 0)
    mr = float(stats.get("FlatSpellBlockMod") or 0)
    hp = float(stats.get("FlatHPPoolMod") or 0)

    if armor >= 25 and ap >= 40:
        return "armadura"
    if mr >= 25 and ap >= 40:
        return "resistência mágica"
    if armor >= 25 and ad >= 25:
        return "armadura"
    if mr >= 25 and ad >= 25:
        return "resistência mágica"

    scores = {
        "poder de habilidade": ap,
        "dano físico": ad,
        "armadura": armor,
        "resistência mágica": mr,
        "vida": hp / 10.0,
    }
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best

    return _foco_secundario(tags_set, stats)


def detectar_efeitos(
    en_description: str,
    stats: dict | None = None,
    tags: list | None = None,
) -> list[str]:
    """Efeitos táticos a partir da descrição EN + stats/tags."""
    raw = en_description or ""
    plain = re.sub(r"<[^>]+>", " ", raw)
    stats = stats or {}
    tags_set = set(tags or [])
    efeitos: list[str] = []

    if re.search(r"\bWounds\b|Grievous", plain, re.I):
        efeitos.append(_EFEITO_CORTA_CURA)

    if re.search(r"\b\d+%\s+Life Steal\b", plain, re.I) or re.search(
        r"\b\d+%\s+Omnivamp\b", plain, re.I
    ):
        efeitos.append(_EFEITO_VAMPIRISMO)

    if "Heal and Shield Power" in raw or re.search(
        r"Heals and Shields on you are increased", plain, re.I
    ):
        efeitos.append(_EFEITO_CURA)

    if (
        re.search(
            r"grants? (?:\w+ ){0,4}(?:a|an)?\s+shield|"
            r"gain (?:\w+ ){0,4}(?:a|an)?\s+shield|"
            r"a\s+\d[\d\s.\-]*shield|"
            r"allies?\s+a\s+.{0,40}shield|"
            r"Spell Shield|"
            r"magic damage Shield|"
            r"damage Shield",
            plain,
            re.I,
        )
        and not re.search(r"reduces? Shields?", plain, re.I)
    ):
        efeitos.append(_EFEITO_ESCUDO)

    mr = float(stats.get("FlatSpellBlockMod") or 0)
    if mr >= 25 or "SpellBlock" in tags_set or "MagicResist" in tags_set:
        efeitos.append(_EFEITO_RM)

    return efeitos


def _build_cache() -> dict:
    version = _fetch_latest_version()
    url_pt = DDRAGON_ITEM_URL_TMPL.format(version=version)
    url_en = DDRAGON_ITEM_URL_TMPL.replace("pt_BR", "en_US").format(version=version)
    r_pt = requests.get(url_pt, timeout=10)
    r_pt.raise_for_status()
    raw_pt = r_pt.json()["data"]
    try:
        r_en = requests.get(url_en, timeout=10)
        r_en.raise_for_status()
        raw_en = r_en.json()["data"]
    except Exception:
        raw_en = {}

    parsed = {}
    for item_id, item in raw_pt.items():
        stats = item.get("stats") or {}
        tags = item.get("tags") or []
        en_desc = (raw_en.get(item_id) or {}).get("description") or item.get("description") or ""
        parsed[item_id] = {
            "name": item.get("name", "Item Desconhecido"),
            "price": item.get("gold", {}).get("total", 0),
            "magic_resist": stats.get("FlatSpellBlockMod", 0),
            "armor": stats.get("FlatArmorMod", 0),
            "ap": stats.get("FlatMagicDamageMod", 0),
            "ad": stats.get("FlatPhysicalDamageMod", 0),
            "is_purchasable": item.get("gold", {}).get("purchasable", False),
            "classificacao": classificar_item(tags, stats),
            "efeitos": detectar_efeitos(en_desc, stats=stats, tags=tags),
        }
    return parsed


def load_items(force_refresh: bool = False) -> dict:
    """Carrega o cache de itens, do disco se existir, senão busca e salva."""
    global _cache
    if _cache is not None and not force_refresh:
        return _cache

    if os.path.exists(ITEMS_FILE) and not force_refresh:
        try:
            with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                disk = json.load(f)
            sample = next(iter(disk.values()), {})
            # Cache antigo sem vampirismo/RM → regenera
            if "efeitos" in sample:
                probe = disk.get("3072") or disk.get("3111") or sample
                efx = probe.get("efeitos") or []
                if "vampirismo" in efx or "resistencia_magica" in efx or probe is sample:
                    # 3072=Sedenta deve ter vamp; 3111=Mercúrio deve ter RM
                    ok_bt = "3072" not in disk or "vampirismo" in (disk.get("3072", {}).get("efeitos") or [])
                    ok_merc = "3111" not in disk or "resistencia_magica" in (
                        disk.get("3111", {}).get("efeitos") or []
                    )
                    if ok_bt and ok_merc:
                        _cache = disk
                        return _cache
        except Exception:
            pass

    try:
        _cache = _build_cache()
        os.makedirs(os.path.dirname(ITEMS_FILE), exist_ok=True)
        with open(ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [item_data] não foi possível buscar itens: {e}")
        _cache = {}

    return _cache


def get_item(item_id: int | str) -> dict | None:
    items = load_items()
    return items.get(str(item_id))


def get_item_classificacao(item_id: int | str) -> str | None:
    item = get_item(item_id)
    if not item:
        return None
    return item.get("classificacao")


def get_item_efeitos(item_id: int | str) -> list[str]:
    item = get_item(item_id)
    if not item:
        return []
    return list(item.get("efeitos") or [])


def item_tem_efeito(item_id: int | str, efeito: str) -> bool:
    return efeito in get_item_efeitos(item_id)


def has_high_magic_resist(item_id: int | str, threshold: int = 30) -> bool:
    item = get_item(item_id)
    return bool(item and item["magic_resist"] >= threshold)
