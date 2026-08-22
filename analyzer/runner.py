"""
runner.py — Análise de histórico invocável por UI/CLI (sem input interativo).
"""

from __future__ import annotations

import io
import os
import sys
import traceback
from contextlib import redirect_stdout
from typing import Callable

import pandas as pd

from config import FILAS, OUTPUT_DIR, QTD_PARTIDAS, RIOT_ID
from api_client import get_match, get_match_ids, get_puuid, get_rank, get_timeline
from extractor import (
    extrair_eventos_mortes,
    extrair_stats_completo,
    extrair_stats_jogador,
)
from heatmap import gerar_mapa_calor
from reporter import imprimir_modo_completo, imprimir_modo_pessoal


ProgressCb = Callable[[str], None] | None


def run_history_analysis(
    modo: str = "pessoal",
    fila_key: str = "1",
    qtd: int | None = None,
    riot_id: str | None = None,
    progress: ProgressCb = None,
) -> dict:
    """
    Roda a análise de histórico de partidas.

    Returns:
        {
          "ok": bool,
          "log": str,           # stdout capturado (relatórios)
          "files": list[str],
          "error": str | None,
          "rank": str,
          "partidas": int,
        }
    """
    def _p(msg: str) -> None:
        if progress:
            progress(msg)

    buf = io.StringIO()
    files: list[str] = []
    rank = ""
    partidas = 0

    try:
        if fila_key not in FILAS:
            return {
                "ok": False,
                "log": "",
                "files": [],
                "error": f"Fila inválida: {fila_key}",
                "rank": "",
                "partidas": 0,
            }
        if modo not in ("pessoal", "completo"):
            return {
                "ok": False,
                "log": "",
                "files": [],
                "error": f"Modo inválido: {modo}",
                "rank": "",
                "partidas": 0,
            }

        nome_fila, queue_id = FILAS[fila_key]
        rid = riot_id or RIOT_ID
        game_name, tag_line = rid.split("#", 1)
        count = qtd or QTD_PARTIDAS

        _p(f"Buscando jogador: {rid}")
        puuid = get_puuid(game_name, tag_line)
        if not puuid:
            from api_client import _last_http_status
            if _last_http_status == 401:
                err = (
                    "API Key inválida ou expirada (HTTP 401). "
                    "Gere outra em https://developer.riotgames.com e atualize o .env (API_KEY=...)."
                )
            elif _last_http_status == 404:
                err = "Riot ID não encontrado. Confira nome#tag (ex.: CadêOWally#wall)."
            else:
                err = f"Falha ao buscar jogador (HTTP {_last_http_status}). Verifique Riot ID e API Key."
            return {
                "ok": False,
                "log": "",
                "files": [],
                "error": err,
                "rank": "",
                "partidas": 0,
            }

        rank = get_rank(puuid)
        _p(f"Elo: {rank}")
        _p(f"Buscando últimas {count} partidas — {nome_fila}...")

        match_ids = get_match_ids(puuid, count, queue_id)
        if not match_ids:
            return {
                "ok": False,
                "log": "",
                "files": [],
                "error": "Nenhuma partida encontrada.",
                "rank": rank,
                "partidas": 0,
            }

        partidas = len(match_ids)
        _p(f"{partidas} partidas encontradas.")

        dados: list = []
        matches: list = []
        todos_mortes: list = []

        for i, mid in enumerate(match_ids, 1):
            _p(f"[{i}/{partidas}] {mid}")
            match = get_match(mid)
            timeline = get_timeline(mid)
            if not match:
                continue
            matches.append(match)
            mortes = extrair_eventos_mortes(match, timeline)
            todos_mortes.extend(mortes)

            if modo == "pessoal":
                stats = extrair_stats_jogador(match, timeline, puuid)
                if stats:
                    dados.append(stats)
            else:
                dados.extend(extrair_stats_completo(match, timeline))

        if not dados:
            return {
                "ok": False,
                "log": "",
                "files": [],
                "error": "Não foi possível extrair dados.",
                "rank": rank,
                "partidas": partidas,
            }

        df = pd.DataFrame(dados)

        with redirect_stdout(buf):
            print("=" * 60)
            print("  League of Legends — Analisador de Partidas")
            print("=" * 60)
            print(f"\nJogador: {rid}")
            print(f"Elo: {rank}")
            print(f"Modo: {modo} | Fila: {nome_fila} | Partidas: {partidas}\n")

            if todos_mortes:
                df_mortes = pd.DataFrame(todos_mortes)
                path = os.path.join(OUTPUT_DIR, "eventos_mortes.csv")
                df_mortes.to_csv(path, index=False)
                print(f"CSV salvo: {path} ({len(todos_mortes)} eventos)")
                files.append(path)
            else:
                df_mortes = pd.DataFrame()

            meu_nome = ""
            if modo == "pessoal":
                imprimir_modo_pessoal(df, df_mortes)
                files.append(os.path.join(OUTPUT_DIR, "partidas_pessoal.csv"))
                files.append(os.path.join(OUTPUT_DIR, "conclusoes_pessoal.txt"))
                for match in matches:
                    for p in match["info"]["participants"]:
                        if p.get("puuid") == puuid:
                            meu_nome = p.get("riotIdGameName", p.get("summonerName", "?"))
                            break
                    if meu_nome:
                        break
            else:
                meu_nome = imprimir_modo_completo(df, puuid, matches, df_mortes)
                files.append(os.path.join(OUTPUT_DIR, "partidas_completo.csv"))
                files.append(os.path.join(OUTPUT_DIR, "conclusoes_completo.txt"))

            if not df_mortes.empty and meu_nome:
                print("\nGerando mapa de calor de mortes...")
                heatmap_path = os.path.join(OUTPUT_DIR, "mapa_calor_mortes.png")
                gerar_mapa_calor(df_mortes, meu_nome, output=heatmap_path)
                files.append(heatmap_path)

            print("\nAnálise concluída!")
            print("\nArquivos gerados:")
            for arq in files:
                print(f"  • {arq}")

        return {
            "ok": True,
            "log": buf.getvalue(),
            "files": files,
            "error": None,
            "rank": rank,
            "partidas": partidas,
        }

    except Exception as exc:
        traceback.print_exc()
        return {
            "ok": False,
            "log": buf.getvalue(),
            "files": files,
            "error": str(exc),
            "rank": rank,
            "partidas": partidas,
        }


def main_cli(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Analisador de histórico LoL")
    parser.add_argument("--modo", choices=("pessoal", "completo"), default="pessoal")
    parser.add_argument("--fila", default="1", choices=sorted(FILAS.keys()))
    parser.add_argument("--qtd", type=int, default=None)
    parser.add_argument("--riot-id", default=None)
    args = parser.parse_args(argv)

    result = run_history_analysis(
        modo=args.modo,
        fila_key=args.fila,
        qtd=args.qtd,
        riot_id=args.riot_id,
        progress=print,
    )
    if result["log"]:
        print(result["log"])
    if not result["ok"]:
        print(f"ERRO: {result['error']}")
        return 1
    return 0


if __name__ == "__main__":
    # Garante imports relativos ao diretório analyzer
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main_cli())
