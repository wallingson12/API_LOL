import os
import pandas as pd
from config import MAP_IMAGE_PATH, OUTPUT_DIR

MAP_SIZE = 14820


def _draw_map(ax):
    """Carrega o mapa oficial ou usa fallback estilizado."""
    ax.set_facecolor("#1a2633")
    ax.set_xlim(0, MAP_SIZE)
    ax.set_ylim(0, MAP_SIZE)
    ax.set_aspect("equal")
    ax.axis("off")

    if os.path.exists(MAP_IMAGE_PATH):
        try:
            from PIL import Image
            img = Image.open(MAP_IMAGE_PATH).convert("RGBA")
            img = img.resize((MAP_SIZE, MAP_SIZE), Image.LANCZOS)
            ax.imshow(img, extent=[0, MAP_SIZE, 0, MAP_SIZE],
                      origin="lower", alpha=0.85, zorder=1, aspect="auto")
            return
        except Exception as e:
            print(f"  ⚠️  Erro ao carregar mapa: {e}")

    # Fallback estilizado
    import matplotlib.patches as patches
    for (p1, p2, rad) in [
        ((2000, 7200), (12800, 7200),  0.15),
        ((7200, 2000), (7200, 12800), -0.15),
    ]:
        ax.add_patch(patches.FancyArrowPatch(
            p1, p2, connectionstyle=f"arc3,rad={rad}",
            color="#1e3a5f", lw=18, alpha=0.6, zorder=1))
    for (x, y, w, h) in [
        (1500, 8000, 4500, 5000), (1500, 1500, 4500, 5000),
        (8800, 8000, 4500, 5000), (8800, 1500, 4500, 5000),
    ]:
        ax.add_patch(patches.Rectangle((x, y), w, h,
            linewidth=0, facecolor="#162a1e", alpha=0.5, zorder=1))
    ax.plot([1200, 13600], [1200, 13600], color="#2d4a2d", lw=12, alpha=0.4, zorder=1)
    ax.plot([1200, 1200],  [7000, 13600], color="#2d4a2d", lw=12, alpha=0.4, zorder=1)
    ax.plot([1200, 7000],  [13600, 13600],color="#2d4a2d", lw=12, alpha=0.4, zorder=1)
    ax.plot([7000, 13600], [1200, 1200],  color="#2d4a2d", lw=12, alpha=0.4, zorder=1)
    ax.plot([13600, 13600],[1200, 7000],  color="#2d4a2d", lw=12, alpha=0.4, zorder=1)
    ax.add_patch(patches.Circle((1200, 1200),   900, color="#1a4a8a", alpha=0.7, zorder=2))
    ax.add_patch(patches.Circle((13600, 13600), 900, color="#8a1a1a", alpha=0.7, zorder=2))
    ax.scatter([1200],  [1200],  c="#4488ff", s=120, zorder=3, marker="*")
    ax.scatter([13600], [13600], c="#ff4444", s=120, zorder=3, marker="*")
    ax.scatter([5000], [10500], c="#aa44ff", s=80, zorder=3, marker="D", alpha=0.8)
    ax.scatter([9800], [4200],  c="#ff8800", s=80, zorder=3, marker="D", alpha=0.8)
    lbl = dict(color="white", fontsize=7, alpha=0.7, ha="center", va="center", zorder=4)
    ax.text(1200,  1200,  "BASE\nAZUL", fontsize=6, color="#88aaff", ha="center", va="center", zorder=4)
    ax.text(13600, 13600, "BASE\nVERM", fontsize=6, color="#ff8888", ha="center", va="center", zorder=4)
    ax.text(5000, 11100, "Baron",  **lbl)
    ax.text(9800,  3600, "Dragon", **lbl)
    ax.text(1200,  7500, "TOP",    **lbl)
    ax.text(7500,  1200, "BOT",    **lbl)
    ax.text(6500,  6500, "MID",    **lbl)


def _draw_heatmap(ax, dados: pd.DataFrame, cor: str, titulo: str, subtitulo: str = ""):
    import numpy as np
    import matplotlib.colors as mcolors
    from scipy.ndimage import gaussian_filter

    _draw_map(ax)
    ax.set_title(f"{titulo}\n{subtitulo}", color="white", fontsize=11,
                 fontweight="bold", pad=8)

    if len(dados) == 0:
        ax.text(MAP_SIZE // 2, MAP_SIZE // 2, "Sem dados",
                color="gray", ha="center", va="center", fontsize=12)
        return

    xs = pd.to_numeric(dados["X"], errors="coerce").dropna().values
    ys = pd.to_numeric(dados["Y"], errors="coerce").dropna().values

    if len(xs) < 2:
        ax.scatter(xs, ys, c=cor, s=60, alpha=0.9, zorder=6)
        return

    heatmap, _, _ = np.histogram2d(
        xs, ys, bins=120,
        range=[[0, MAP_SIZE], [0, MAP_SIZE]]
    )
    heatmap = gaussian_filter(heatmap.T, sigma=4)
    base    = mcolors.to_rgb(cor)
    cmap    = mcolors.LinearSegmentedColormap.from_list("c",
        [(0, 0, 0, 0)] + [(base[0], base[1], base[2], a / 255) for a in range(1, 256)])

    ax.imshow(heatmap, extent=[0, MAP_SIZE, 0, MAP_SIZE],
              origin="lower", cmap=cmap, alpha=0.85, zorder=5, aspect="auto")

    for fase, fc in [("Early", "#ffff00"), ("Mid", "#ff8800"), ("Late", "#ff4444")]:
        sub = dados[dados["Fase"] == fase]
        if len(sub):
            ax.scatter(pd.to_numeric(sub["X"], errors="coerce"),
                       pd.to_numeric(sub["Y"], errors="coerce"),
                       c=fc, s=18, alpha=0.6, zorder=7, label=fase,
                       edgecolors="black", linewidths=0.3)

    ax.legend(loc="upper left", fontsize=7, framealpha=0.4,
              labelcolor="white", facecolor="#0d1117", edgecolor="#444")
    ax.text(300, 300, f"n={len(xs)}", color="white", fontsize=8, zorder=8,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#0d1117", alpha=0.7))


def gerar_mapa_calor(df_mortes: pd.DataFrame, meu_nome: str, output: str | None = None):
    if output is None:
        output = os.path.join(OUTPUT_DIR, "mapa_calor_mortes.png")
    try:
        import matplotlib.pyplot as plt

        minhas_mortes = df_mortes[df_mortes["Victim"] == meu_nome]
        minhas_kills  = df_mortes[df_mortes["Killer"] == meu_nome]

        fig, axes = plt.subplots(1, 3, figsize=(22, 8))
        fig.patch.set_facecolor("#0d1117")
        fig.suptitle(f"Mapa de Calor de Mortes — {meu_nome}",
                     color="white", fontsize=17, fontweight="bold", y=1.01)

        _draw_heatmap(axes[0], df_mortes,    "#ff3333", "Todas as mortes",  f"({len(df_mortes)} eventos)")
        _draw_heatmap(axes[1], minhas_mortes,"#ff8800", "Suas mortes",      f"({len(minhas_mortes)} mortes)")
        _draw_heatmap(axes[2], minhas_kills, "#00ff88", "Suas kills",       f"({len(minhas_kills)} kills)")

        fig.text(0.5, -0.02,
                 "● Early (0–14min)   ● Mid (15–24min)   ● Late (25+min)",
                 ha="center", color="#aaaaaa", fontsize=9)

        plt.tight_layout(pad=2)
        plt.savefig(output, dpi=160, bbox_inches="tight", facecolor="#0d1117")
        plt.close()
        print(f"  🗺️  Mapa de calor salvo: {output}")

    except ImportError as e:
        print(f"  ⚠️  Biblioteca faltando: {e}")
        print("     Execute: pip install matplotlib scipy Pillow")
    except Exception as e:
        print(f"  ⚠️  Erro ao gerar mapa: {e}")
