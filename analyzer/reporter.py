"""
reporter.py — Relatório de análise no estilo coaching (o que treinar), não dump de stats.
CSVs continuam completos; o texto impresso prioriza hábito e decisão.
"""

from __future__ import annotations

import os

import pandas as pd
from tabulate import tabulate

from conclusions import (
    _tip_vs,
    conclusoes_completo,
    conclusoes_pessoal,
    imprimir_conclusoes,
    salvar_conclusoes,
)
from config import OUTPUT_DIR


def _mean(df: pd.DataFrame, col: str) -> float | None:
    if col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    return float(s.mean()) if not s.empty else None


def _wins(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Vitória"] == "✅"] if "Vitória" in df.columns else df.iloc[0:0]


def _losses(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Vitória"] != "✅"] if "Vitória" in df.columns else df.iloc[0:0]


def _section(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _bullet(text: str) -> None:
    print(f"  • {text}")


def _leitura_forma(df: pd.DataFrame) -> None:
    """Snapshot curto + leitura de jogador, não lista de 20 métricas."""
    n = len(df)
    w = int((_wins(df)).shape[0])
    wr = (w / n * 100) if n else 0
    kda = _mean(df, "KDA")
    d = _mean(df, "D")
    kp = _mean(df, "KP%")
    cs = _mean(df, "CS/min")
    vis = _mean(df, "Visão")
    gpm = _mean(df, "Gold/min")
    morto = _mean(df, "Tempo Morto (s)")
    dpm = _mean(df, "Dano/min") or (_mean(df, "Dano") or 0) / max(_mean(df, "Duração (min)") or 1, 1)

    _section("FORMA — LEITURA RÁPIDA")
    print(f"  {n} partidas · {w}W/{n - w}L · WR {wr:.0f}%")
    print(
        f"  KDA {kda:.2f}  |  Mortes {d:.1f}/jogo  |  KP {kp:.0f}%  |  "
        f"CS/min {cs:.1f}  |  Visão {vis:.0f}  |  Gold/min {gpm:.0f}"
        if None not in (kda, d, kp, cs, vis, gpm)
        else "  (métricas incompletas)"
    )
    if morto is not None:
        print(f"  Tempo morto médio: ~{int(morto)}s/jogo")

    # Leituras
    if d is not None and d >= 4.5:
        _bullet("Mortes altas: o elo sobe mais fácil reduzindo death do que caçando pentakill.")
    elif d is not None and d <= 2.5:
        _bullet("Sobrevivência ok — use isso pra estar vivo em objetivo, não pra farmar side sozinho forever.")

    if kp is not None and kp < 40:
        _bullet("KP baixo = jogo paralelo. Shove → olha mapa → rotate. Não some mid 20 min.")
    elif kp is not None and kp >= 55:
        _bullet("KP alto: você está nas lutas certas — mantenha, sem virar deathball suicida.")

    if cs is not None and cs < 5.5:
        _bullet("Farm fraco pra rota: entre rotates limpa wave. Andar sem wave = behind silencioso.")
    if vis is not None and vis < 14:
        _bullet("Visão baixa: pink toda volta da base + 1 clear de ward por recall. Barato e sobe WR.")
    if morto is not None and morto >= 180:
        _bullet("Muito tempo morto = time 4v5. Vale mais 1 vida que 1 kill forçada.")


def _fases(df: pd.DataFrame) -> None:
    cols = ["Kills Early", "Kills Mid", "Kills Late", "Mortes Early", "Mortes Mid", "Mortes Late"]
    if not all(c in df.columns for c in cols):
        return
    _section("FASES DO JOGO — ONDE VOCÊ GANHA/PERDE")
    ke, km, kl = _mean(df, "Kills Early"), _mean(df, "Kills Mid"), _mean(df, "Kills Late")
    me, mm, ml = _mean(df, "Mortes Early"), _mean(df, "Mortes Mid"), _mean(df, "Mortes Late")
    print(f"  {'':<8} {'Early':>8} {'Mid':>8} {'Late':>8}")
    print(f"  {'Kills':<8} {ke or 0:>8.1f} {km or 0:>8.1f} {kl or 0:>8.1f}")
    print(f"  {'Mortes':<8} {me or 0:>8.1f} {mm or 0:>8.1f} {ml or 0:>8.1f}")

    if me and me >= 1.5:
        _bullet(
            "Early sangrando: sem visão no rio, não empurra 3ª wave sozinho. "
            "Farm sob torre > placa doada."
        )
    if mm and mm >= me and mm >= 1.5:
        _bullet("Mid-game: chegue 30s antes do dragão/arauto. Chegar atrasado = enter free.")
    if (ke or 0) + (km or 0) + (kl or 0) > 0:
        pico = max(("early", ke or 0), ("mid", km or 0), ("late", kl or 0), key=lambda x: x[1])
        _bullet(f"Seu pico de kills é no {pico[0]} — jogue o draft/tempo em volta disso, não force o oposto.")

    g10 = _mean(df, "Gold@10")
    g15 = _mean(df, "Gold@15")
    if g10 is not None and g15 is not None:
        print(f"  Gold médio @10: {g10:.0f}  |  @15: {g15:.0f}")
        if g15 < g10 * 1.35:
            _bullet("Gold trava entre 10–15: você está morrendo ou andando sem wave. Reset + shove.")


def _win_loss(df: pd.DataFrame) -> None:
    w, l = _wins(df), _losses(df)
    if w.empty or l.empty or len(df) < 4:
        return
    _section("VITÓRIA × DERROTA — O QUE MUDA O RESULTADO")
    rows = []
    for col, label in (
        ("D", "Mortes"),
        ("KP%", "KP%"),
        ("Visão", "Visão"),
        ("CS/min", "CS/min"),
        ("Gold@10", "Gold@10"),
        ("Mortes Early", "Mortes early"),
        ("Dano", "Dano"),
        ("Control Wards Colocados", "Pinks"),
    ):
        mw, ml = _mean(w, col), _mean(l, col)
        if mw is None or ml is None:
            continue
        rows.append((label, mw, ml, mw - ml))
    if not rows:
        return
    print(f"  {'Métrica':<16} {'Win':>8} {'Loss':>8} {'Δ':>8}")
    for label, mw, ml, diff in rows:
        print(f"  {label:<16} {mw:>8.1f} {ml:>8.1f} {diff:>+8.1f}")

    # Coaching direto
    d_w, d_l = _mean(w, "D"), _mean(l, "D")
    if d_w is not None and d_l is not None and d_l >= d_w + 1:
        _bullet(
            f"Derrota = +{d_l - d_w:.1f} mortes. Meta da fila: teto de {max(2, int(d_w) + 1)} mortes. "
            "Kill a menos importa menos que death a menos."
        )
    v_w, v_l = _mean(w, "Visão"), _mean(l, "Visão")
    if v_w is not None and v_l is not None and v_w >= v_l + 2:
        _bullet("Wins vêm com mais visão. Ward não é 'suporte only' — é win condition sua.")


def _quem_te_mata(df_mortes: pd.DataFrame | None, jogador: str | None) -> None:
    if df_mortes is None or df_mortes.empty or not jogador or "Victim" not in df_mortes.columns:
        return
    mine = df_mortes[df_mortes["Victim"] == jogador]
    if mine.empty:
        return

    _section("MORTES — HÁBITO (NÃO SÓ 'MORRI PRO X')")
    print(f"  {len(mine)} mortes na timeline · minuto médio {_mean(mine, 'Minuto') or 0:.0f}")

    if "Fase" in mine.columns:
        fase = mine["Fase"].value_counts()
        bits = ", ".join(f"{k} {int(v)} ({v/len(mine)*100:.0f}%)" for k, v in fase.items())
        print(f"  Por fase: {bits}")

    if "Assistentes" in mine.columns:
        solo = float((mine["Assistentes"].fillna("").astype(str).str.strip() == "").mean())
        print(f"  Mortes solo (sem assist): {solo*100:.0f}%")
        if solo >= 0.45:
            _bullet("Quase metade solo = overextend. Sem flash + sem visão = você é o objetivo.")
        elif solo <= 0.25:
            _bullet("Maioria em gank/luta: respeite sumiço de jg/mid; wave alta sem ping = isca.")

    if "Killer_Campeão" in mine.columns:
        top = mine["Killer_Campeão"].value_counts().head(5)
        print("\n  Quem mais te matou → o que fazer:")
        for champ, cnt in top.items():
            tip = _tip_vs(str(champ))
            if tip:
                print(f"  • {champ} ({cnt}x): {tip.split('— ', 1)[-1] if '— ' in tip else tip}")
            else:
                print(
                    f"  • {champ} ({cnt}x): estude o CD do engage; "
                    "guarde flash/imunidade só pra esse botão."
                )


def _pool_e_build(df: pd.DataFrame) -> None:
    _section("POOL E BUILD")
    if "Campeão" in df.columns:
        grp = (
            df.groupby("Campeão")
            .agg(
                Jogos=("Partida", "count"),
                WR=("Vitória", lambda x: (x == "✅").mean() * 100),
                KDA=("KDA", "mean"),
                Mortes=("D", "mean"),
                KP=("KP%", "mean"),
            )
            .reset_index()
            .sort_values("Jogos", ascending=False)
        )
        grp["WR"] = grp["WR"].round(0).astype(int)
        grp["KDA"] = grp["KDA"].round(2)
        grp["Mortes"] = grp["Mortes"].round(1)
        grp["KP"] = grp["KP"].round(0).astype(int)
        print(tabulate(grp.head(8), headers="keys", tablefmt="rounded_outline", showindex=False))
        if len(grp) >= 2:
            best = grp.loc[grp["WR"].idxmax()]
            worst = grp.loc[grp["WR"].idxmin()]
            if best["Campeão"] != worst["Campeão"] and best["Jogos"] >= 2 and worst["Jogos"] >= 2:
                _bullet(
                    f"Melhor momento: {best['Campeão']} (WR {best['WR']}%). "
                    f"Revisar: {worst['Campeão']} (WR {worst['WR']}%) — "
                    "abra 1 replay de loss e pause 20s antes de cada morte."
                )

    if "Lane" in df.columns:
        lane = df["Lane"].value_counts()
        if not lane.empty:
            _bullet(f"Rota mais jogada: {lane.index[0]} ({int(lane.iloc[0])}/{len(df)}).")

    item_cols = [c for c in ("Item0", "Item1", "Item2", "Item3", "Item4", "Item5") if c in df.columns]
    if item_cols:
        todos = pd.Series(df[item_cols].values.flatten())
        todos = todos[todos.astype(str).str.strip() != ""]
        if not todos.empty:
            print("\n  Itens mais frequentes (inventário final):")
            for nome, cnt in todos.value_counts().head(6).items():
                print(f"    {nome}: {cnt}x")
            joined = " ".join(todos.astype(str)).lower()
            d = _mean(df, "D")
            if d and d >= 3 and "zhonya" not in joined and "ampulheta" not in joined:
                if any(x in joined for x in ("luden", "sombria", "shadowflame", "chama")):
                    _bullet(
                        "Build bem glass-cannon com mortes demais. "
                        "Encaixe Zhonya/defensivo no 2º–3º item — AP morto não carrega."
                    )


def _ultimas(df: pd.DataFrame, limit: int = 12) -> None:
    cols = [c for c in (
        "Data", "Campeão", "Lane", "Vitória", "K", "D", "A", "KDA", "KP%", "CS/min", "Visão", "Duração (min)"
    ) if c in df.columns]
    if not cols:
        return
    _section("ÚLTIMAS PARTIDAS")
    print(tabulate(df[cols].head(limit), headers="keys", tablefmt="rounded_outline", showindex=False))
    _bullet("CSV completo tem timeline, objetivos, pings e itens por jogo — use pra drill-down.")


def _objetivos_resumo(df: pd.DataFrame) -> None:
    if "Dragões" not in df.columns:
        return
    _section("OBJETIVOS — VOCÊ APARECE?")
    drag = _mean(df, "Dragões")
    bar = _mean(df, "Barões")
    torres = _mean(df, "Torres Participação") or _mean(df, "Torres Destruídas")
    dano_obj = _mean(df, "Dano Objetivos")
    print(
        f"  Dragões/jogo {drag or 0:.1f}  |  Barões {bar or 0:.1f}  |  "
        f"Torres (part.) {torres or 0:.1f}  |  Dano em objetivo {int(dano_obj or 0):,}"
    )
    if drag is not None and drag < 0.5:
        _bullet("Quase sumido em dragão. Timer: ande 15–20s antes do spawn, não no ping de luta.")
    elif drag is not None and drag >= 1.0:
        _bullet("Presença em dragão ok — mantenha e converta em torre, não em chase mid.")


# ─────────────────────────────────────────
# MODO PESSOAL
# ─────────────────────────────────────────
def imprimir_modo_pessoal(df: pd.DataFrame, df_mortes: pd.DataFrame | None = None):
    path = os.path.join(OUTPUT_DIR, "partidas_pessoal.csv")
    df.to_csv(path, index=False)
    print(f"\n💾 CSV salvo: {path}")

    jogador = str(df["Jogador"].iloc[0]) if "Jogador" in df.columns and not df.empty else None

    # 1) Coaching primeiro — é o que o jogador precisa ler
    lines = conclusoes_pessoal(df, df_mortes, jogador)
    imprimir_conclusoes(lines, "COACHING — O QUE TREINAR AGORA")
    salvar_conclusoes(lines, "conclusoes_pessoal.txt")

    # 2) Contexto que sustenta o coaching
    _leitura_forma(df)
    _fases(df)
    _win_loss(df)
    _quem_te_mata(df_mortes, jogador)
    _objetivos_resumo(df)
    _pool_e_build(df)
    _ultimas(df)

    print("\n" + "-" * 60)
    print("  Dados brutos (todas as colunas) estão no CSV.")
    print("  Relatório acima = o que treinar; CSV = prova.")
    print("-" * 60)


# ─────────────────────────────────────────
# MODO COMPLETO
# ─────────────────────────────────────────
def imprimir_modo_completo(
    df: pd.DataFrame,
    puuid_jogador: str,
    matches: list,
    df_mortes: pd.DataFrame | None = None,
) -> str:
    path = os.path.join(OUTPUT_DIR, "partidas_completo.csv")
    df.to_csv(path, index=False)
    print(f"\n💾 CSV salvo: {path}")

    meu_nome = ""
    for match in matches:
        for p in match["info"]["participants"]:
            if p.get("puuid") == puuid_jogador:
                meu_nome = p.get("riotIdGameName", p.get("summonerName", "?"))
                break
        if meu_nome:
            break

    meus = df[df["Jogador"] == meu_nome].copy()

    lines = conclusoes_completo(df, meus, df_mortes, meu_nome or None)
    imprimir_conclusoes(lines, "COACHING — O QUE TREINAR AGORA")
    salvar_conclusoes(lines, "conclusoes_completo.txt")

    if not meus.empty:
        _leitura_forma(meus)

    _section("VOCÊ × LOBBY — ONDE ESTÁ O GAP")
    comps = [
        ("KDA", "KDA", True),
        ("KP%", "KP%", True),
        ("CS/min", "CS/min", True),
        ("Dano", "Dano", True),
        ("Visão", "Visão", True),
        ("Gold/min", "Gold/min", True),
        ("Tempo Morto (s)", "Tempo morto", False),
        ("Tempo CC em Inimigos (s)", "CC (s)", True),
        ("Dragões", "Dragões", True),
    ]
    print(f"  {'Métrica':<14} {'Você':>8} {'Lobby':>8} {'Gap':>8}  Leitura")
    print("  " + "-" * 56)
    for col, label, high_good in comps:
        if col not in df.columns or meus.empty or col not in meus.columns:
            continue
        eu = _mean(meus, col)
        med = _mean(df, col)
        if eu is None or med is None:
            continue
        gap = eu - med
        if high_good:
            if gap >= med * 0.08:
                leitura = "ponto forte — não troque por ego"
            elif gap <= -med * 0.08:
                leitura = "treinar isso sobe elo"
            else:
                leitura = "no pacote"
        else:
            if gap > abs(med) * 0.08:
                leitura = "você morre/fica off demais"
            elif gap < -abs(med) * 0.08:
                leitura = "vivo mais que o lobby — bom"
            else:
                leitura = "no pacote"
        sinal = "+" if gap >= 0 else ""
        print(f"  {label:<14} {eu:>8.1f} {med:>8.1f} {sinal}{gap:>7.1f}  {leitura}")

    _quem_te_mata(df_mortes, meu_nome or None)
    if not meus.empty:
        _fases(meus)
        _win_loss(meus)
        _pool_e_build(meus)
        _ultimas(meus)

    _section("CAMPEÕES MAIS COMUNS NAS SUAS PARTIDAS (LOBBY)")
    if "Campeão" in df.columns:
        for champ, count in df["Campeão"].value_counts().head(8).items():
            wr = (df[df["Campeão"] == champ]["Vitória"] == "✅").mean() * 100
            print(f"  {champ:<18} {count:>3}x  WR lobby {wr:.0f}%")
        _bullet("WR do lobby no champ ≠ matchup seu — use só pra saber o meta da fila.")

    print("\n" + "-" * 60)
    print("  CSV completo tem os 10 jogadores por partida.")
    print("-" * 60)

    return meu_nome
