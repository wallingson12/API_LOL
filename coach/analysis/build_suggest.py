"""
build_suggest.py — Sugestão de item por regra (ameaça inimiga → o que comprar).
Sem IA: 1 necessidade por vez, 1 fala por partida.
"""

from __future__ import annotations

from data.champion_data import get_champion_profile_by_name
from data.item_data import get_item, get_item_efeitos

# Componentes / lendários por perfil (IDs Data Dragon)
_GW_AP = (3916, 3165)       # Orbe → Morellonomicon
_GW_AD = (6609,)            # Serrespada Quimiopunk (e similares)
_GW_TANK = (3075,)          # Armadura de Espinhos
_ZHONYA = (3157,)           # Ampulheta de Zhonya
_VOID = (3135, 4630)        # Cajado do Vazio / Joia da Ruína (componente)

# Prioridade: menor = fala primeiro se várias necessidades
_RULES = (
    {
        "need": "corta_cura",
        "priority": 1,
        "enemy_effects": ("vampirismo", "cura"),
        "min_enemies": 1,
        "reason": "inimigo com cura/vamp",
    },
    {
        "need": "pen_magica",
        "priority": 2,
        "enemy_effects": ("resistencia_magica",),
        "min_enemies": 2,
        "reason": "time com resistência mágica",
        "requires_tags": ("Mage",),
    },
    {
        "need": "zhonya",
        "priority": 3,
        "enemy_effects": (),  # especial: muitos assassinos AD — via tags dos champs
        "min_enemies": 0,
        "reason": "burst físico no time",
        "requires_tags": ("Mage",),
        "enemy_champ_tags": ("Assassin",),
        "min_tag_champs": 2,
    },
)


def _my_item_ids(me: dict | None) -> list[int]:
    if not me:
        return []
    out: list[int] = []
    for raw in me.get("items") or []:
        iid = raw.get("itemID")
        if iid is None:
            continue
        try:
            out.append(int(iid))
        except (TypeError, ValueError):
            continue
    return out


def _has_efeito(item_ids: list[int], efeito: str) -> bool:
    for iid in item_ids:
        if efeito in get_item_efeitos(iid):
            return True
    return False


def _has_any_item(item_ids: list[int], candidates: tuple[int, ...]) -> bool:
    have = set(item_ids)
    return any(c in have for c in candidates)


def _my_tags(me: dict | None) -> set[str]:
    if not me:
        return set()
    profile = get_champion_profile_by_name(me.get("championName") or "")
    if not profile:
        return set()
    return {str(t) for t in (profile.get("tags") or [])}


def _enemy_names_with_effects(board: dict, effects: tuple[str, ...]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for eff in effects:
        for row in board.get(eff) or []:
            champ = (row.get("champion") or "").strip()
            if champ and champ not in seen:
                seen.add(champ)
                names.append(champ)
    return names


def _count_enemies_with_tags(enemies: list[dict], tags: tuple[str, ...]) -> int:
    want = {t.lower() for t in tags}
    n = 0
    for e in enemies:
        profile = get_champion_profile_by_name(e.get("championName") or "")
        if not profile:
            continue
        etags = {str(t).lower() for t in (profile.get("tags") or [])}
        if etags & want:
            n += 1
    return n


def _pick_item(need: str, my_tags: set[str]) -> tuple[int, str] | None:
    """Retorna (id, nome) do item sugerido."""
    if need == "corta_cura":
        if "Tank" in my_tags and "Mage" not in my_tags and "Marksman" not in my_tags:
            pool = _GW_TANK
        elif "Mage" in my_tags or "Support" in my_tags:
            pool = _GW_AP
        else:
            pool = _GW_AD
    elif need == "pen_magica":
        pool = _VOID
    elif need == "zhonya":
        pool = _ZHONYA
    else:
        return None
    for iid in pool:
        meta = get_item(iid)
        if meta and meta.get("name"):
            return iid, str(meta["name"])
    return None


def _already_covered(need: str, item_ids: list[int]) -> bool:
    if need == "corta_cura":
        return _has_efeito(item_ids, "corta_cura")
    if need == "pen_magica":
        return _has_any_item(item_ids, _VOID)
    if need == "zhonya":
        return _has_any_item(item_ids, _ZHONYA)
    return False


def current_suggestion(
    board: dict | None,
    me: dict | None,
    enemies: list[dict] | None = None,
) -> dict | None:
    """Sugestão ativa pra UI (pode mudar se você já comprou o counter)."""
    board = board or {}
    enemies = enemies or []
    item_ids = _my_item_ids(me)
    my_tags = _my_tags(me)

    candidates: list[tuple[int, dict]] = []
    for rule in _RULES:
        need = rule["need"]
        req = rule.get("requires_tags") or ()
        if req and not (my_tags & set(req)):
            continue
        if _already_covered(need, item_ids):
            continue

        if rule.get("enemy_champ_tags"):
            n = _count_enemies_with_tags(enemies, tuple(rule["enemy_champ_tags"]))
            if n < int(rule.get("min_tag_champs") or 2):
                continue
            who = f"{n} assassinos"
        else:
            effects = tuple(rule.get("enemy_effects") or ())
            names = _enemy_names_with_effects(board, effects)
            if len(names) < int(rule.get("min_enemies") or 1):
                continue
            who = ", ".join(names[:2])

        picked = _pick_item(need, my_tags)
        if not picked:
            continue
        iid, nome = picked
        candidates.append((
            int(rule["priority"]),
            {
                "need": need,
                "item_id": iid,
                "item_name": nome,
                "reason": rule["reason"],
                "who": who,
                "text": f"Compre {nome}. {rule['reason'].capitalize()}: {who}.",
                "short": f"Compre {nome}.",
                "ui": f"{nome}  ·  {who}",
            },
        ))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


class BuildSuggestTracker:
    """Emite alerta de voz 1x por necessidade coberta na partida."""

    def __init__(self) -> None:
        self._spoken: set[str] = set()

    def reset(self) -> None:
        self._spoken.clear()

    def alerts(
        self,
        board: dict | None,
        me: dict | None,
        enemies: list[dict] | None = None,
    ) -> list[dict]:
        sug = current_suggestion(board, me, enemies)
        if not sug:
            return []
        need = sug["need"]
        if need in self._spoken:
            return []
        # só fala quando a ameaça acabou de aparecer (board já tem efeito)
        # primeira vez que a necessidade existe
        self._spoken.add(need)
        return [{
            "type": "build_suggest",
            "need": need,
            "item_name": sug["item_name"],
            "text": sug["short"],
            "key": f"build_suggest_{need}",
        }]
