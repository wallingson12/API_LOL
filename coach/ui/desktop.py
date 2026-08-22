"""Interface desktop — visual de aplicativo oficial (League / ferramenta pro)."""

from __future__ import annotations

import math
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
from tkinter import ttk

from analysis.enemy_item_board import format_board_lines
from analysis.history_bridge import FILAS_UI, run_match_history
from app_state import STATE
from engine import CoachEngine

# Direção visual: navy profundo + ouro (cliente Riot-adjacent), sem glow/roxo
C = {
    "bg": "#070a10",
    "bg2": "#0c111a",
    "surface": "#101722",
    "panel": "#141c28",
    "panel_hi": "#1a2433",
    "line": "#243044",
    "line_soft": "#1a2433",
    "text": "#f4f1ea",
    "muted": "#9aa6b8",
    "dim": "#6b778c",
    "gold": "#c9a227",
    "gold_hi": "#e0bc4a",
    "gold_dim": "#3d3418",
    "live": "#3dcf8e",
    "live_dim": "#1a3d2e",
    "danger": "#d45454",
    "danger_hi": "#e66a6a",
    "danger_dim": "#3a1f1f",
    "warn": "#e0a84a",
    "info": "#5b9fd4",
    "input": "#0a0f16",
    "cura": "#e8a0a8",
    "vamp": "#e06b6b",
    "escudo": "#7eb0d4",
    "rm": "#6ec4b8",
    "gw": "#e0b84a",
}

STATUS_FG = {
    "stopped": C["muted"],
    "idle": C["muted"],
    "champ_select": C["warn"],
    "in_game": C["live"],
    "post_game": C["info"],
}

BOARD_ACCENT = {
    "cura": C["cura"],
    "vampirismo": C["vamp"],
    "escudo": C["escudo"],
    "resistencia_magica": C["rm"],
    "corta_cura": C["gw"],
}


class CoachDesktopUI:
    def __init__(self, engine: CoachEngine):
        self.engine = engine
        self.root = tk.Tk()
        self.root.title("Coach")
        self.root.geometry("1080x720")
        self.root.minsize(900, 620)
        self.root.configure(bg=C["bg"])
        try:
            self.root.tk.call("tk", "scaling", 1.2)
        except tk.TclError:
            pass

        self._history_running = False
        self._pulse_phase = 0.0
        self._active_tab = "coach"
        self._fonts()
        self._style()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        threading.Thread(target=self.engine.preload, daemon=True).start()
        self._tick()
        self._pulse()

    # ── typography ─────────────────────────────────────
    def _fonts(self) -> None:
        display = self._pick_font(
            "Bahnschrift", "Segoe UI Semibold", "Candara", "Calibri", "Segoe UI",
        )
        body = self._pick_font("Bahnschrift", "Segoe UI", "Calibri", "Tahoma")
        mono = self._pick_font("Cascadia Mono", "Consolas", "Courier New")

        self.f_brand = tkfont.Font(family=display, size=28, weight="bold")
        self.f_brand_sub = tkfont.Font(family=body, size=9)
        self.f_nav = tkfont.Font(family=body, size=11, weight="bold")
        self.f_h2 = tkfont.Font(family=display, size=14, weight="bold")
        self.f_label = tkfont.Font(family=body, size=8)
        self.f_body = tkfont.Font(family=body, size=10)
        self.f_btn = tkfont.Font(family=body, size=10, weight="bold")
        self.f_metric = tkfont.Font(family=display, size=18, weight="bold")
        self.f_metric_lg = tkfont.Font(family=display, size=24, weight="bold")
        self.f_mono = tkfont.Font(family=mono, size=10)

    def _pick_font(self, *names: str) -> str:
        try:
            families = set(tkfont.families())
        except tk.TclError:
            families = set()
        for name in names:
            if name in families:
                return name
        return names[-1]

    def _font_exists(self, name: str) -> bool:
        try:
            return name in tkfont.families()
        except tk.TclError:
            return False

    def _style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "App.TCombobox",
            fieldbackground=C["input"],
            background=C["panel"],
            foreground=C["text"],
            arrowcolor=C["gold"],
            bordercolor=C["line"],
            lightcolor=C["line"],
            darkcolor=C["line"],
            padding=8,
        )
        style.map(
            "App.TCombobox",
            fieldbackground=[("readonly", C["input"])],
            foreground=[("readonly", C["text"])],
            selectbackground=[("readonly", C["gold_dim"])],
            selectforeground=[("readonly", C["text"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=C["panel_hi"],
            troughcolor=C["bg2"],
            bordercolor=C["bg2"],
            arrowcolor=C["dim"],
        )

    # ── widgets ────────────────────────────────────────
    def _btn(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        kind: str = "primary",
        state: str = "normal",
        padx: int = 22,
        pady: int = 11,
    ) -> tk.Button:
        colors = {
            "primary": (C["gold"], C["gold_hi"], C["bg"]),
            "danger": (C["danger"], C["danger_hi"], C["text"]),
            "ghost": (C["panel_hi"], C["line"], C["text"]),
            "nav": (C["surface"], C["panel_hi"], C["muted"]),
            "nav_on": (C["panel_hi"], C["panel_hi"], C["gold"]),
        }
        bg, hover, fg = colors.get(kind, colors["primary"])
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            disabledforeground=C["dim"],
            font=self.f_btn,
            relief="flat",
            bd=0,
            padx=padx,
            pady=pady,
            cursor="hand2",
            state=state,
        )

        def on_enter(_e):
            if str(btn["state"]) != "disabled":
                btn.configure(bg=hover)

        def on_leave(_e):
            if str(btn["state"]) != "disabled":
                btn.configure(bg=bg)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def _field_label(self, parent: tk.Misc, text: str) -> None:
        tk.Label(
            parent,
            text=text.upper(),
            font=self.f_label,
            fg=C["dim"],
            bg=parent.cget("bg"),
        ).pack(anchor="w", pady=(0, 5))

    def _entry(self, parent: tk.Misc, var: tk.StringVar, width: int = 24) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=var,
            width=width,
            font=self.f_body,
            bg=C["input"],
            fg=C["text"],
            insertbackground=C["gold"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=C["line"],
            highlightcolor=C["gold"],
        )

    # ── layout ─────────────────────────────────────────
    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=C["bg"])
        shell.pack(fill="both", expand=True)

        # Sidebar
        side = tk.Frame(shell, bg=C["surface"], width=200)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        brand_box = tk.Frame(side, bg=C["surface"])
        brand_box.pack(fill="x", padx=22, pady=(28, 8))
        tk.Label(
            brand_box, text="COACH", font=self.f_brand,
            fg=C["text"], bg=C["surface"],
        ).pack(anchor="w")
        tk.Label(
            brand_box, text="LEAGUE  ·  AO VIVO", font=self.f_brand_sub,
            fg=C["gold"], bg=C["surface"],
        ).pack(anchor="w", pady=(2, 0))

        tk.Frame(side, bg=C["line"], height=1).pack(fill="x", padx=18, pady=(18, 14))

        self._tab_btns: dict[str, tk.Button] = {}
        nav = tk.Frame(side, bg=C["surface"])
        nav.pack(fill="x", padx=12)
        for key, label in (("coach", "  Coach ao vivo"), ("history", "  Histórico")):
            btn = tk.Button(
                nav,
                text=label,
                anchor="w",
                command=lambda k=key: self._show_tab(k),
                font=self.f_nav,
                relief="flat",
                bd=0,
                padx=14,
                pady=12,
                cursor="hand2",
                bg=C["surface"],
                fg=C["muted"],
                activebackground=C["panel_hi"],
                activeforeground=C["gold"],
            )
            btn.pack(fill="x", pady=2)
            self._tab_btns[key] = btn

        # Status na base da sidebar
        foot = tk.Frame(side, bg=C["surface"])
        foot.pack(side="bottom", fill="x", padx=22, pady=22)
        row = tk.Frame(foot, bg=C["surface"])
        row.pack(fill="x")
        self.status_dot = tk.Canvas(row, width=12, height=12, bg=C["surface"], highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 8))
        self._dot_id = self.status_dot.create_oval(2, 2, 10, 10, fill=C["dim"], outline="")
        self.header_status = tk.StringVar(value="Parado")
        tk.Label(
            row, textvariable=self.header_status, font=self.f_body,
            fg=C["muted"], bg=C["surface"], anchor="w", wraplength=140, justify="left",
        ).pack(side="left", fill="x", expand=True)

        # Main
        main = tk.Frame(shell, bg=C["bg"])
        main.pack(side="left", fill="both", expand=True)

        # Header
        header = tk.Frame(main, bg=C["bg2"], height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.page_title = tk.StringVar(value="Coach ao vivo")
        tk.Label(
            header, textvariable=self.page_title,
            font=self.f_h2, fg=C["text"], bg=C["bg2"],
        ).pack(side="left", padx=28, pady=22)
        self.page_sub = tk.StringVar(value="Alertas de voz e itens inimigos")
        tk.Label(
            header, textvariable=self.page_sub,
            font=self.f_body, fg=C["dim"], bg=C["bg2"],
        ).pack(side="left", padx=(4, 0), pady=22)
        tk.Frame(main, bg=C["gold"], height=2).pack(fill="x")

        body = tk.Frame(main, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=28, pady=(8, 24))

        self.tab_coach = tk.Frame(body, bg=C["bg"])
        self.tab_history = tk.Frame(body, bg=C["bg"])
        self._tab_frames = {"coach": self.tab_coach, "history": self.tab_history}

        self._build_coach_tab()
        self._build_history_tab()
        self._show_tab("coach")

    def _build_coach_tab(self) -> None:
        # Controles
        bar = tk.Frame(self.tab_coach, bg=C["bg"])
        bar.pack(fill="x", pady=(0, 18))

        self.btn_start = self._btn(bar, "Iniciar coach", self._start_coach, kind="primary")
        self.btn_start.pack(side="left", padx=(0, 10))
        self.btn_stop = self._btn(bar, "Parar", self._stop_coach, kind="danger", state="disabled")
        self.btn_stop.pack(side="left")

        # Métricas — faixa contínua, não “dashboard de cards”
        strip = tk.Frame(self.tab_coach, bg=C["panel"], highlightbackground=C["line"], highlightthickness=1)
        strip.pack(fill="x", pady=(0, 18))

        self.status_var = tk.StringVar(value="Coach parado")
        self.time_var = tk.StringVar(value="0:00")
        self.dragon_var = tk.StringVar(value="0 × 0")
        self.champ_var = tk.StringVar(value="—")

        specs = (
            ("STATUS", self.status_var, None, C["text"]),
            ("TEMPO", self.time_var, None, C["text"]),
            ("DRAGÕES", self.dragon_var, self.f_metric_lg, C["info"]),
            ("CAMPEÃO / ROTA", self.champ_var, None, C["text"]),
        )
        self.status_value = None
        for i, (title, var, font, fg) in enumerate(specs):
            cell = tk.Frame(strip, bg=C["panel"])
            cell.grid(row=0, column=i, sticky="nsew", padx=0)
            if i > 0:
                tk.Frame(cell, bg=C["line"], width=1).pack(side="left", fill="y", pady=16)
            inner = tk.Frame(cell, bg=C["panel"])
            inner.pack(fill="both", expand=True, padx=22, pady=18)
            tk.Label(inner, text=title, font=self.f_label, fg=C["dim"], bg=C["panel"]).pack(anchor="w")
            lab = tk.Label(
                inner, textvariable=var, font=font or self.f_metric,
                fg=fg, bg=C["panel"], anchor="w",
            )
            lab.pack(anchor="w", pady=(8, 0))
            if i == 0:
                self.status_value = lab
            strip.columnconfigure(i, weight=1, uniform="m")

        # Quadro de itens
        board = tk.Frame(self.tab_coach, bg=C["panel"], highlightbackground=C["line"], highlightthickness=1)
        board.pack(fill="both", expand=True)

        head = tk.Frame(board, bg=C["panel"])
        head.pack(fill="x", padx=22, pady=(16, 10))
        tk.Label(
            head, text="ITENS INIMIGOS", font=self.f_label,
            fg=C["dim"], bg=C["panel"],
        ).pack(side="left")
        tk.Label(
            head, text="atualiza ao vivo  ·  voz na compra",
            font=self.f_label, fg=C["dim"], bg=C["panel"],
        ).pack(side="right")

        cols = tk.Frame(board, bg=C["panel"])
        cols.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.board_texts: dict[str, tk.Text] = {}
        titles = (
            ("cura", "CURA"),
            ("vampirismo", "VAMPIRISMO"),
            ("escudo", "ESCUDO"),
            ("resistencia_magica", "RES. MÁGICA"),
            ("corta_cura", "CORTA CURA"),
        )
        for i, (key, title) in enumerate(titles):
            cell = tk.Frame(cols, bg=C["bg2"])
            cell.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            accent = tk.Frame(cell, bg=BOARD_ACCENT[key], height=3)
            accent.pack(fill="x")
            inner = tk.Frame(cell, bg=C["bg2"])
            inner.pack(fill="both", expand=True, padx=12, pady=10)
            tk.Label(
                inner, text=title, font=self.f_label,
                fg=BOARD_ACCENT[key], bg=C["bg2"],
            ).pack(anchor="w")
            box = tk.Text(
                inner,
                height=14,
                width=16,
                font=self.f_body,
                fg=C["text"],
                bg=C["bg2"],
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                wrap="word",
                cursor="arrow",
            )
            box.insert("1.0", "—")
            box.configure(state="disabled")
            box.pack(anchor="w", fill="both", expand=True, pady=(8, 0))
            self.board_texts[key] = box
            cols.columnconfigure(i, weight=1, uniform="ib")

    def _build_history_tab(self) -> None:
        form = tk.Frame(
            self.tab_history, bg=C["panel"],
            highlightbackground=C["line"], highlightthickness=1,
        )
        form.pack(fill="x", pady=(0, 16))
        inner = tk.Frame(form, bg=C["panel"])
        inner.pack(fill="x", padx=22, pady=20)

        tk.Label(
            inner, text="Análise de histórico", font=self.f_h2,
            fg=C["text"], bg=C["panel"],
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 14))

        boxes = [tk.Frame(inner, bg=C["panel"]) for _ in range(4)]
        for i, box in enumerate(boxes):
            box.grid(row=1, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            inner.columnconfigure(i, weight=1)

        self._field_label(boxes[0], "Riot ID")
        self.riot_id_var = tk.StringVar(value="CadêOWally#wall")
        self._entry(boxes[0], self.riot_id_var, 26).pack(fill="x")

        self._field_label(boxes[1], "Modo")
        self.modo_var = tk.StringVar(value="pessoal")
        ttk.Combobox(
            boxes[1], textvariable=self.modo_var,
            values=["pessoal", "completo"], state="readonly",
            style="App.TCombobox", width=14,
        ).pack(fill="x")

        self._field_label(boxes[2], "Fila")
        self.fila_labels = [f"{k} — {v}" for k, v in FILAS_UI.items()]
        self.fila_var = tk.StringVar(value=self.fila_labels[0])
        ttk.Combobox(
            boxes[2], textvariable=self.fila_var,
            values=self.fila_labels, state="readonly",
            style="App.TCombobox", width=22,
        ).pack(fill="x")

        self._field_label(boxes[3], "Partidas")
        self.qtd_var = tk.StringVar(value="20")
        self._entry(boxes[3], self.qtd_var, 8).pack(fill="x")

        actions = tk.Frame(inner, bg=C["panel"])
        actions.grid(row=2, column=0, columnspan=4, sticky="w", pady=(18, 0))
        self.btn_history = self._btn(actions, "Analisar", self._run_history, kind="primary")
        self.btn_history.pack(side="left")
        self.history_status = tk.StringVar(value="")
        tk.Label(
            actions, textvariable=self.history_status,
            font=self.f_body, fg=C["muted"], bg=C["panel"],
        ).pack(side="left", padx=16)

        report = tk.Frame(
            self.tab_history, bg=C["panel"],
            highlightbackground=C["line"], highlightthickness=1,
        )
        report.pack(fill="both", expand=True)
        head = tk.Frame(report, bg=C["panel"])
        head.pack(fill="x", padx=22, pady=(14, 6))
        tk.Label(head, text="SAÍDA", font=self.f_label, fg=C["dim"], bg=C["panel"]).pack(side="left")

        wrap = tk.Frame(report, bg=C["panel"])
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        scroll = ttk.Scrollbar(wrap, style="Vertical.TScrollbar")
        scroll.pack(side="right", fill="y")
        self.history_box = tk.Text(
            wrap,
            wrap="word",
            font=self.f_mono,
            bg=C["input"],
            fg=C["text"],
            insertbackground=C["gold"],
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            yscrollcommand=scroll.set,
        )
        self.history_box.pack(fill="both", expand=True)
        scroll.config(command=self.history_box.yview)

    def _show_tab(self, key: str) -> None:
        self._active_tab = key
        titles = {
            "coach": ("Coach ao vivo", "Alertas de voz e itens inimigos"),
            "history": ("Histórico", "Análise de partidas recentes"),
        }
        title, sub = titles.get(key, ("", ""))
        self.page_title.set(title)
        self.page_sub.set(sub)

        for name, frame in self._tab_frames.items():
            if name == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        for name, btn in self._tab_btns.items():
            if name == key:
                btn.configure(bg=C["panel_hi"], fg=C["gold"], activebackground=C["panel_hi"])
            else:
                btn.configure(bg=C["surface"], fg=C["muted"], activebackground=C["panel_hi"])

    # ── actions ────────────────────────────────────────
    def _start_coach(self) -> None:
        if self.engine.start():
            self.btn_start.configure(state="disabled", bg=C["gold_dim"], fg=C["dim"])
            self.btn_stop.configure(state="normal", bg=C["danger"])

    def _stop_coach(self) -> None:
        self.engine.stop()
        self.btn_start.configure(state="normal", bg=C["gold"], fg=C["bg"])
        self.btn_stop.configure(state="disabled", bg=C["danger_dim"])

    def _append_history(self, line: str) -> None:
        self.history_box.insert(tk.END, line + "\n")
        self.history_box.see(tk.END)

    def _run_history(self) -> None:
        if self._history_running:
            return
        riot_id = self.riot_id_var.get().strip()
        if "#" not in riot_id:
            messagebox.showerror("Riot ID", "Use o formato Nome#TAG")
            return
        try:
            qtd = int(self.qtd_var.get().strip())
        except ValueError:
            messagebox.showerror("Quantidade", "Qtd de partidas inválida.")
            return

        fila_key = self.fila_var.get().split(" — ", 1)[0].strip()
        modo = self.modo_var.get().strip()

        self._history_running = True
        self.btn_history.configure(state="disabled", bg=C["gold_dim"], fg=C["dim"])
        self.history_status.set("Analisando…")
        self.history_box.delete("1.0", tk.END)
        self._append_history(f"{riot_id}  ·  {modo}  ·  fila {fila_key}  ·  {qtd} partidas\n")

        def worker():
            result = run_match_history(
                modo=modo,
                fila_key=fila_key,
                qtd=qtd,
                riot_id=riot_id,
                on_line=lambda line: self.root.after(0, lambda l=line: self._append_history(l)),
            )

            def done():
                self._history_running = False
                self.btn_history.configure(state="normal", bg=C["gold"], fg=C["bg"])
                if result["ok"]:
                    self.history_status.set("Concluído")
                else:
                    self.history_status.set(f"Erro: {result.get('error')}")
                    if result.get("error"):
                        self._append_history(f"\nERRO: {result['error']}")

            self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _set_dot(self, color: str) -> None:
        self.status_dot.itemconfigure(self._dot_id, fill=color)

    def _pulse(self) -> None:
        """Pulso suave no indicador quando em partida."""
        try:
            data = STATE.snapshot()
            if data.get("status") == "in_game":
                self._pulse_phase += 0.18
                # oscila brilho do live
                t = (math.sin(self._pulse_phase) + 1) / 2
                # interpola live ↔ live_dim visualmente via fill fixed + size feel
                color = C["live"] if t > 0.35 else C["live_dim"]
                self._set_dot(color)
            else:
                self._pulse_phase = 0.0
        except Exception:
            pass
        finally:
            self.root.after(120, self._pulse)

    def _tick(self) -> None:
        try:
            data = STATE.snapshot()
            self.status_var.set(data["status_label"])
            self.header_status.set(data["status_label"])
            self.time_var.set(data["game_time_fmt"])
            self.dragon_var.set(data["dragon_score"])
            champ = data["my_champion"] or "—"
            role = data["my_role"] or "—"
            self.champ_var.set(f"{champ}  ·  {role}")

            try:
                board_text = format_board_lines(data.get("enemy_item_board"))
                for key, box in getattr(self, "board_texts", {}).items():
                    text = board_text.get(key) or "—"
                    current = box.get("1.0", "end-1c")
                    if current != text:
                        box.configure(state="normal")
                        box.delete("1.0", "end")
                        box.insert("1.0", text)
                        box.configure(state="disabled")
            except Exception:
                pass

            status = data["status"]
            fg = STATUS_FG.get(status, C["muted"])
            if self.status_value is not None:
                self.status_value.configure(fg=fg)
            if status != "in_game":
                self._set_dot(fg)

            if data["coach_running"]:
                self.btn_start.configure(state="disabled", bg=C["gold_dim"], fg=C["dim"])
                self.btn_stop.configure(state="normal", bg=C["danger"])
            else:
                self.btn_start.configure(state="normal", bg=C["gold"], fg=C["bg"])
                self.btn_stop.configure(state="disabled", bg=C["danger_dim"])
        except Exception:
            pass
        finally:
            self.root.after(400, self._tick)

    def _on_close(self) -> None:
        self.engine.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_ui(engine: CoachEngine | None = None) -> None:
    eng = engine or CoachEngine()
    CoachDesktopUI(eng).run()
