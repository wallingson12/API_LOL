"""
conclusions.py — Conclusões no estilo coaching (hábito + matchup), não só estatística.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from config import OUTPUT_DIR

_CHAMPS_FILE = Path(__file__).resolve().parent.parent / "coach" / "data" / "champions.json"
_champ_by_name: dict[str, dict] | None = None

# Dicas extras quando o danger_tip do JSON é genérico demais p/ o hábito
_KILLER_HABITS: dict[str, str] = {
    "Tristana": (
        "Tristana: não fique em cima dela com bomba (E) carregando — "
        "saia do AA range, force ela gastar o pulo (W) sem reset, e só reengaje depois."
    ),
    "Yasuo": (
        "Yasuo: não jogue skillshot no windwall; espere o dash (E) acabar o stack "
        "e lute fora do tornado (Q3)."
    ),
    "Yone": (
        "Yone: quando ele usar E (corpo espiritual), guarde CC/burst pro retorno — "
        "não gaste tudo no clone."
    ),
    "Zed": (
        "Zed: guarde flash/imunidade pro R; compre Zhonya se ele te caça todo jogo."
    ),
    "Fizz": (
        "Fizz: não fique com wave empurrada sem visão; o R dele pune mid imóvel."
    ),
    "Warwick": (
        "Warwick: se estiver <50% vida, ele te sente — baseie ou junte com o time "
        "antes de overextend."
    ),
    "MasterYi": (
        "Master Yi: não fique sozinho late; compre corta-cura e pelem em grupo."
    ),
    "XinZhao": (
        "Xin Zhao: ele trava com E+W — não lute no mato sem visão; pelem quando o E cair."
    ),
    "Jinx": (
        "Jinx: fora do foguete (W) e do chomp (R) ela é frágil — "
        "não chute no face dela com trap no chão."
    ),
    "MissFortune": (
        "Miss Fortune: não fique alinhado pro R; entre pelo flanco ou após o ult."
    ),
    "Vladimir": (
        "Vladimir: troca curta; ele ganha luta longa com pool (W) e cura — "
        "compre corta-cura se ele escalar."
    ),
    "Sylas": (
        "Sylas: não gaste R perto dele se o R for forte; ele rouba e vira a luta."
    ),
    "Akali": (
        "Akali: não entre na fumaça sem visão; espere energia baixa / R2 pra reengajar."
    ),
    "Katarina": (
        "Katarina: guarde CC pro salto (E); se errou o CC, saia — ela reseta em kill."
    ),
    "Leblanc": (
        "LeBlanc: não chase o clone; volte pra torre quando o W dela estiver up."
    ),
}


def _load_champs() -> dict[str, dict]:
    global _champ_by_name
    if _champ_by_name is not None:
        return _champ_by_name
    by_name: dict[str, dict] = {}
    if _CHAMPS_FILE.exists():
        try:
            with open(_CHAMPS_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            for meta in (raw or {}).values():
                name = (meta or {}).get("id") or (meta or {}).get("name")
                if name:
                    by_name[str(name).lower()] = meta
                    disp = (meta or {}).get("name")
                    if disp:
                        by_name[str(disp).lower()] = meta
        except Exception:
            pass
    _champ_by_name = by_name
    return by_name


def _tip_vs(champion: str) -> str | None:
    """Dica prática vs campeão que mais te mata."""
    if not champion or champion == "?":
        return None
    key = champion.strip()
    if key in _KILLER_HABITS:
        return _KILLER_HABITS[key]
    # tenta sem espaços / case
    for k, v in _KILLER_HABITS.items():
        if k.lower() == key.lower():
            return v
    profile = _load_champs().get(key.lower())
    if not profile:
        return None
    danger = (profile.get("danger_tip") or "").strip()
    tips = profile.get("enemy_tips") or []
    extra = ""
    if tips:
        # pega a dica mais curta/útil
        extra = str(tips[0]).strip()
        if len(extra) > 140:
            extra = extra[:137] + "..."
    if danger and extra:
        return f"{key}: {danger} → {extra}"
    if danger:
        return f"{key}: {danger}"
    if extra:
        return f"{key}: {extra}"
    return None


def _safe_mean(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.mean()) if not s.empty else None


def _win_mask(df: pd.DataFrame) -> pd.Series:
    return df["Vitória"] == "✅"


def _limitar(lines: list[str], max_n: int = 8) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ln in lines:
        if not ln or ln in seen:
            continue
        seen.add(ln)
        out.append(ln)
        if len(out) >= max_n:
            break
    return out


def _habitos_basicos(df: pd.DataFrame) -> list[tuple[int, str]]:
    """(prioridade, texto). Prioridade menor = mais urgente."""
    scored: list[tuple[int, str]] = []
    n = len(df)
    if n == 0:
        return scored

    deaths = _safe_mean(df["D"]) if "D" in df.columns else None
    kp = _safe_mean(df["KP%"]) if "KP%" in df.columns else None
    cs = _safe_mean(df["CS/min"]) if "CS/min" in df.columns else None
    visao = _safe_mean(df["Visão"]) if "Visão" in df.columns else None
    me = _safe_mean(df["Mortes Early"]) if "Mortes Early" in df.columns else None
    mm = _safe_mean(df["Mortes Mid"]) if "Mortes Mid" in df.columns else None
    drag = _safe_mean(df["Dragões"]) if "Dragões" in df.columns else None
    tempo_morto = _safe_mean(df["Tempo Morto (s)"]) if "Tempo Morto (s)" in df.columns else None

    # Vitória vs derrota → o que muda o resultado
    if "Vitória" in df.columns and n >= 4:
        w, l = df[_win_mask(df)], df[~_win_mask(df)]
        if not w.empty and not l.empty:
            dw = _safe_mean(w["D"]) if "D" in df.columns else None
            dl = _safe_mean(l["D"]) if "D" in df.columns else None
            vw = _safe_mean(w["Visão"]) if "Visão" in df.columns else None
            vl = _safe_mean(l["Visão"]) if "Visão" in df.columns else None
            if dw is not None and dl is not None and dl >= dw + 1.0:
                scored.append((
                    1,
                    f"Nas derrotas você morre bem mais ({dl:.1f} vs {dw:.1f}). "
                    f"Meta da próxima sessão: no máximo {max(2, int(dw) + 1)} mortes/jogo — "
                    "cada morte a menos vale mais que chase de kill.",
                ))
            if vw is not None and vl is not None and vw >= vl + 2:
                scored.append((
                    2,
                    f"Nas vitórias sua visão sobe ({vw:.0f} vs {vl:.0f}). "
                    "Hábito: pink + ward de rio/pixel antes de qualquer rotate — "
                    "visão está correlacionada com suas wins.",
                ))

    if me is not None and me >= 1.5:
        scored.append((
            1,
            f"Você sangra no early ({me:.1f} mortes antes dos 15). "
            "Regra: sem ward no rio/lateral, não empurra a 3ª wave sozinho; "
            "aceita farm sob torre se o jungle inimigo sumiu.",
        ))
    elif mm is not None and mm >= 1.5:
        scored.append((
            2,
            f"Mortes no mid-game ({mm:.1f}/jogo). "
            "Antes de dragão/arauto: chega 30s cedo com visão, não teleporte em cima da luta já começada.",
        ))

    if deaths is not None and deaths >= 5:
        scored.append((
            1,
            f"Média de {deaths:.1f} mortes/jogo. "
            "Pare de jogar pelo highlight: se o time não tá junto, farm e wave — não invente 1v2.",
        ))

    if kp is not None and kp < 40:
        scored.append((
            3,
            f"KP {kp:.0f}% — você joga isolado demais. "
            "Depois de shove, olhe side/objetivo; uma rotate a tempo vale mais que +10 CS.",
        ))
    elif kp is not None and kp >= 55 and (deaths or 0) <= 3:
        scored.append((4, f"KP alto ({kp:.0f}%) com poucas mortes — continue priorizando luta certa, não toda luta."))

    if cs is not None and cs < 5.5:
        scored.append((
            4,
            f"CS/min {cs:.1f} tá baixo pra rota. "
            "Entre rotates: limpa wave rápido e volta — não fique andando no mapa sem motivo.",
        ))

    if visao is not None and visao < 12:
        scored.append((
            3,
            f"Visão {visao:.0f} score/jogo. "
            "Compre control ward toda volta da base; limpe 1 ward inimiga por recall.",
        ))

    if drag is not None and drag < 0.4:
        scored.append((
            4,
            "Quase não aparece em dragão. Anote o timer: 15s antes já tem que estar andando — "
            "não só quando o ping vermelho sobe.",
        ))

    if tempo_morto is not None and tempo_morto >= 200:
        scored.append((
            2,
            f"~{int(tempo_morto)}s morto por jogo. "
            "Menos death timer = mais XP/gold que qualquer kill forçada.",
        ))

    return scored


def _habitos_mortes(df_mortes: pd.DataFrame | None, jogador: str | None) -> list[tuple[int, str]]:
    if df_mortes is None or df_mortes.empty or not jogador or "Victim" not in df_mortes.columns:
        return []
    mine = df_mortes[df_mortes["Victim"] == jogador]
    if mine.empty:
        return []

    scored: list[tuple[int, str]] = []
    total = len(mine)

    if "Assistentes" in mine.columns:
        solo = float((mine["Assistentes"].fillna("").astype(str).str.strip() == "").mean())
        if solo >= 0.45:
            scored.append((
                1,
                f"{solo*100:.0f}% das suas mortes foram sozinho (sem assist inimiga). "
                "Isso é overextend/ego — se não tem flash e não tem visão, volta 1 tela.",
            ))
        elif solo <= 0.25:
            scored.append((
                2,
                "A maioria das mortes vem de gank/luta juntos. "
                "Hábito: ping de sumido + não fique na wave alta quando o mid/jg some.",
            ))

    if "Killer_Campeão" in mine.columns:
        top = mine["Killer_Campeão"].value_counts().head(3)
        for champ, cnt in top.items():
            if cnt < 2:
                continue
            tip = _tip_vs(str(champ))
            if tip:
                scored.append((1, f"Te matou {cnt}x — {tip}"))
            else:
                scored.append((
                    2,
                    f"{champ} te matou {cnt}x. "
                    "Estude o CD do engage dele e guarde flash/imunidade só pra isso.",
                ))

    if "Fase" in mine.columns and total >= 5:
        fase = mine["Fase"].value_counts()
        top_fase = str(fase.index[0])
        pct = float(fase.iloc[0] / total)
        if top_fase == "Early" and pct >= 0.45:
            scored.append((
                1,
                f"{pct*100:.0f}% das mortes no early. "
                "Primeiros 10 min: farm > placa > kill. Placa sem visão = doação de snowball.",
            ))
        elif top_fase == "Mid" and pct >= 0.4:
            scored.append((
                2,
                f"{pct*100:.0f}% das mortes no mid. "
                "Lute só com seu time no objetivo — chegar atrasado = enter de graça.",
            ))

    if "Minuto" in mine.columns:
        m = _safe_mean(mine["Minuto"])
        if m is not None and m <= 12:
            scored.append((
                3,
                f"Minuto médio das mortes: {m:.0f}. "
                "Seu jogo decide cedo — foque pathing do jungle inimigo nesses minutos.",
            ))

    return scored


def _build_sugestao(df: pd.DataFrame, df_mortes: pd.DataFrame | None, jogador: str | None) -> str | None:
    """Sugestão de item/hábito de build com base em quem te mata / inventário."""
    killers: list[str] = []
    if df_mortes is not None and not df_mortes.empty and jogador and "Victim" in df_mortes.columns:
        mine = df_mortes[df_mortes["Victim"] == jogador]
        if "Killer_Campeão" in mine.columns and not mine.empty:
            killers = [str(c) for c in mine["Killer_Campeão"].value_counts().head(5).index]

    adish = {"Yasuo", "Yone", "Zed", "Talon", "Qiyana", "MasterYi", "Tristana", "Jinx",
             "MissFortune", "Lucian", "Pyke", "Rengar", "KhaZix", "XinZhao", "Warwick"}
    apish = {"Syndra", "Ahri", "Fizz", "Leblanc", "Annie", "Brand", "Vladimir", "Viktor", "Anivia"}
    healers = {"Warwick", "Vladimir", "Aatrox", "Sylas", "Mundomedicamento", "Soraka", "Yuumi",
               "Swain", "Mundo", "DrMundo", "Nilah"}

    # nomes Riot às vezes sem espaço
    norm = {k.replace(" ", "") for k in killers}
    if norm & {x.replace(" ", "") for x in healers}:
        return (
            "Vários kills em cima de você vêm de campeão com cura/sustain — "
            "antecipe Morello/Quimtech (corta-cura) no 2º/3º item, não só no late."
        )
    if len(norm & {x.replace(" ", "") for x in adish}) >= 2:
        return (
            "Quem te caça é majoritariamente AD (assassino/ADC). "
            "Considere Zhonya / armadura cedo se estiver sendo oneshot — "
            "vidinha sem armadura não segura burst."
        )
    if len(norm & {x.replace(" ", "") for x in apish}) >= 2:
        return (
            "Burst mágico te pegando muito. "
            "Banshee ou RM situacional (ex.: manto cedo) se o mid/jg AP estiver à frente."
        )

    # inventário próprio
    item_cols = [c for c in ("Item0", "Item1", "Item2", "Item3", "Item4", "Item5") if c in df.columns]
    if item_cols:
        todos = pd.Series(df[item_cols].values.flatten()).astype(str)
        join = " ".join(todos.tolist()).lower()
        if "luden" in join or "eco de luden" in join:
            if "zhonya" not in join and "ampulheta" not in join:
                if deaths := _safe_mean(df["D"]) if "D" in df.columns else None:
                    if deaths and deaths >= 3:
                        return (
                            "Build bem ofensiva (Luden etc.) com mortes demais. "
                            "Encaixe Zhonya ou item defensivo no 2º/3º — dano morto não ganha jogo."
                        )
    return None


def conclusoes_pessoal(
    df: pd.DataFrame,
    df_mortes: pd.DataFrame | None = None,
    jogador: str | None = None,
) -> list[str]:
    if df is None or df.empty:
        return ["Sem dados suficientes pra coaching."]

    jogador = jogador or (str(df["Jogador"].iloc[0]) if "Jogador" in df.columns else None)
    n = len(df)
    wins = int(_win_mask(df).sum()) if "Vitória" in df.columns else 0

    scored: list[tuple[int, str]] = []
    scored.append((
        0,
        f"Foco da sessão ({n} jogos, WR {wins}/{n}): "
        "corrija 1 hábito abaixo por fila — não tente consertar tudo de uma vez.",
    ))
    scored.extend(_habitos_basicos(df))
    scored.extend(_habitos_mortes(df_mortes, jogador))

    build = _build_sugestao(df, df_mortes, jogador)
    if build:
        scored.append((2, build))

    if "Campeão" in df.columns:
        main = df["Campeão"].value_counts().index[0]
        n_main = int(df["Campeão"].value_counts().iloc[0])
        if n_main >= max(3, n // 2):
            scored.append((
                5,
                f"Pool concentrada em {main}. "
                "Na review: abra 1 replay onde você morreu early e pause no caminho do jungle — "
                "o erro costuma estar 20s antes da morte.",
            ))

    scored.sort(key=lambda x: x[0])
    return _limitar([t for _, t in scored], max_n=8)


def conclusoes_completo(
    df: pd.DataFrame,
    meus: pd.DataFrame,
    df_mortes: pd.DataFrame | None = None,
    jogador: str | None = None,
) -> list[str]:
    if meus is None or meus.empty:
        return ["Sem as suas linhas no dataset completo."]

    lines = conclusoes_pessoal(meus, df_mortes, jogador)

    # 1 insight de lobby, bem concreto
    lobby_bits: list[str] = []
    for col, label, high_good, tip in (
        ("Dano", "dano", True, "você já carrega dano — o gap é sobrevivência/visão, não build full AP."),
        ("KP%", "KP", True, "entre nas lutas do time; dano sem KP vira farm inútil."),
        ("Tempo Morto (s)", "tempo morto", False, "ficar vivo mais que o lobby já é vantagem."),
        ("Visão", "visão", True, "ward win games em elo baixo/médio mais que mecânica."),
        ("CS/min", "CS/min", True, "farm entre rotates pra não ficar behind sem perceber."),
    ):
        if col not in df.columns or col not in meus.columns:
            continue
        eu = _safe_mean(meus[col])
        med = _safe_mean(df[col])
        if eu is None or med is None or med == 0:
            continue
        if high_good and eu < med * 0.92:
            lobby_bits.append(f"Abaixo do lobby em {label} ({eu:.1f} vs {med:.1f}): {tip}")
        elif not high_good and eu > med * 1.08:
            lobby_bits.append(f"Acima do lobby em {label} ({eu:.1f} vs {med:.1f}): {tip}")
        elif high_good and eu > med * 1.1:
            lobby_bits.append(f"Acima do lobby em {label} — bom. Não troque isso por ego fight.")

    if lobby_bits:
        # troca a linha 0 de foco se necessário, ou anexa no topo após foco
        return _limitar([lines[0], lobby_bits[0], *lines[1:]], max_n=8)
    return lines


def imprimir_conclusoes(lines: list[str], titulo: str = "COACHING — O QUE TREINAR") -> None:
    print("\n" + "=" * 60)
    print(f"  {titulo}")
    print("=" * 60)
    if not lines:
        print("  (sem conclusões)")
        return
    for i, ln in enumerate(lines, 1):
        print(f"  {i}. {ln}")


def salvar_conclusoes(lines: list[str], filename: str = "conclusoes.txt") -> str:
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write("COACHING — O QUE TREINAR\n")
        f.write("=" * 40 + "\n\n")
        for i, ln in enumerate(lines, 1):
            f.write(f"{i}. {ln}\n")
    print(f"\n💾 Conclusões salvas: {path}")
    return path
