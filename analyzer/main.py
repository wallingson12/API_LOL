"""CLI interativo do analisador (menus no terminal)."""

from config import FILAS
from menus import selecionar_fila, selecionar_modo
from runner import run_history_analysis


def main():
    print("=" * 60)
    print("  League of Legends — Analisador de Partidas")
    print("=" * 60)

    modo = selecionar_modo()
    nome_fila, _ = selecionar_fila()
    fila_key = next(k for k, (n, _) in FILAS.items() if n == nome_fila)

    result = run_history_analysis(modo=modo, fila_key=fila_key, progress=print)
    if result["log"]:
        print(result["log"])
    if not result["ok"]:
        print(f"\n❌ {result['error']}")
        return

    print("\n✅ Análise concluída!")


if __name__ == "__main__":
    main()
