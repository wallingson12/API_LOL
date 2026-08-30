"""Aba Avisos — editor de dicas, oponentes, canais e dados oficiais."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from alerts.channels import CHANNEL_LABELS, EDITABLE_ALERT_TYPES, DEFAULT_CHANNELS
from data.champion_data import get_champion_profile_by_name, load_champion_profiles
from data.knowledge import DRAGONS, WARDS, LANE_MACRO, WAVE_TIPS, RUNE_BY_TAG
from data.notices import (
    get_champion_note,
    load_store,
    save_store,
    set_champion_note,
    set_channel_override,
)


def _sorted_champ_names() -> list[str]:
    profiles = load_champion_profiles()
    names = sorted(
        {(p.get("name") or "").strip() for p in profiles.values() if p.get("name")}
    )
    return [n for n in names if n]


class NoticesPanel:
    def __init__(self, parent: tk.Misc, ui, colors: dict) -> None:
        self.ui = ui
        self.colors = colors
        self._champ_names = _sorted_champ_names() or ["Ahri"]

        self.frame = parent
        self._build()

    def _build(self) -> None:
        C = self.colors
        ui = self.ui

        nav = tk.Frame(self.frame, bg=C["bg"])
        nav.pack(fill="x", pady=(0, 12))
        self._section = tk.StringVar(value="oponentes")
        for key, label in (
            ("oponentes", "Oponentes"),
            ("dragoes", "Dragões"),
            ("wards", "Wards"),
            ("runas", "Runas"),
            ("lane", "Lane"),
            ("canais", "Canais"),
        ):
            btn = ui._btn(
                nav, label, lambda k=key: self._show(k),
                kind="ghost", padx=12, pady=8,
            )
            btn.pack(side="left", padx=(0, 8))

        self.body = tk.Frame(self.frame, bg=C["bg"])
        self.body.pack(fill="both", expand=True)
        self._panels: dict[str, tk.Frame] = {}
        for key, builder in (
            ("oponentes", self._build_opponents),
            ("dragoes", self._build_dragons),
            ("wards", self._build_wards),
            ("runas", self._build_runes),
            ("lane", self._build_lane),
            ("canais", self._build_channels),
        ):
            panel = tk.Frame(self.body, bg=C["bg"])
            builder(panel)
            self._panels[key] = panel
        self._show("oponentes")

    def _show(self, key: str) -> None:
        self._section.set(key)
        for name, frame in self._panels.items():
            if name == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    def _card(self, parent: tk.Misc) -> tk.Frame:
        C = self.colors
        box = tk.Frame(
            parent, bg=C["panel"],
            highlightbackground=C["line"], highlightthickness=1,
        )
        box.pack(fill="both", expand=True)
        inner = tk.Frame(box, bg=C["panel"])
        inner.pack(fill="both", expand=True, padx=22, pady=18)
        return inner

    def _text(self, parent: tk.Misc, height: int = 8, *, expand: bool = True) -> tk.Text:
        C = self.colors
        box = tk.Text(
            parent,
            height=height,
            wrap="word",
            font=self.ui.f_body,
            bg=C["input"],
            fg=C["text"],
            insertbackground=C["gold"],
            relief="flat",
            padx=10,
            pady=8,
            highlightthickness=1,
            highlightbackground=C["line"],
            highlightcolor=C["gold"],
        )
        box.pack(fill="both" if expand else "x", expand=expand)
        return box

    def _get(self, widget: tk.Text) -> str:
        return widget.get("1.0", "end-1c").strip()

    def _set(self, widget: tk.Text, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value or "")

    def _freeze_text(self, box: tk.Text) -> None:
        box.bind("<Key>", lambda _e: "break")
        box.bind("<<Paste>>", lambda _e: "break")
        box.bind("<<Cut>>", lambda _e: "break")

    # ── oponentes ──────────────────────────────────────
    def _build_opponents(self, parent: tk.Frame) -> None:
        C = self.colors
        ui = self.ui
        inner = self._card(parent)
        self._champ_editing = False

        row = tk.Frame(inner, bg=C["panel"])
        row.pack(fill="x", pady=(0, 10))
        ui._field_label(row, "Campeão")
        self.champ_var = tk.StringVar(value=self._champ_names[0])
        combo = ttk.Combobox(
            row, textvariable=self.champ_var, values=self._champ_names,
            state="readonly", style="App.TCombobox", width=28,
        )
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", lambda _e: self._on_champ_pick())

        ui._field_label(inner, "Dica")
        self.danger_var = tk.StringVar()
        self.danger_entry = ui._entry(inner, self.danger_var, 60)
        self.danger_entry.pack(fill="x", pady=(0, 8))

        actions = tk.Frame(inner, bg=C["panel"])
        actions.pack(fill="x")
        ui._btn(actions, "Editar", self._edit_champion, kind="ghost").pack(side="left")
        ui._btn(actions, "Salvar", self._save_champion, kind="primary").pack(side="left", padx=8)
        ui._btn(actions, "Cancelar", self._cancel_champion, kind="ghost").pack(side="left")

        self._load_champion()
        self._set_champ_edit(False)

    def _set_champ_edit(self, on: bool) -> None:
        self._champ_editing = on
        state = "normal" if on else "readonly"
        self.danger_entry.configure(state=state)

    def _on_champ_pick(self) -> None:
        self._set_champ_edit(False)
        self._load_champion()

    def _edit_champion(self) -> None:
        self._set_champ_edit(True)

    def _cancel_champion(self) -> None:
        self._set_champ_edit(False)
        self._load_champion()

    def _load_champion(self) -> None:
        name = self.champ_var.get().strip()
        note = get_champion_note(name)
        profile = get_champion_profile_by_name(name) or {}
        editing = self._champ_editing
        self.danger_entry.configure(state="normal")
        self.danger_var.set(note.get("danger_tip") or profile.get("danger_tip") or "")
        if not editing:
            self._set_champ_edit(False)

    def _save_champion(self) -> None:
        if not self._champ_editing:
            return
        name = self.champ_var.get().strip()
        set_champion_note(name, {
            "danger_tip": self.danger_var.get().strip(),
        })
        self._set_champ_edit(False)

    # ── referências ────────────────────────────────────
    def _build_dragons(self, parent: tk.Frame) -> None:
        inner = self._card(parent)
        box = self._text(inner, 18)
        lines = []
        for key, data in DRAGONS.items():
            lines.append(
                f"{data['name']}\n"
                f"  Stack: {data['stack']}\n"
                f"  {data['soul']}\n"
                f"  {data['rift']}\n"
                f"  Jogada: {data['play']}\n"
            )
        self._set(box, "\n".join(lines))
        self._freeze_text(box)

    def _build_wards(self, parent: tk.Frame) -> None:
        inner = self._card(parent)
        box = self._text(inner, 18)
        lines = []
        for ward in WARDS:
            lines.append(
                f"{ward['name']}\n"
                f"  Duração: {ward['duration']}\n"
                f"  {ward['use']}\n"
                f"  Quando: {ward['when']}\n"
            )
        self._set(box, "\n".join(lines))
        self._freeze_text(box)

    def _build_runes(self, parent: tk.Frame) -> None:
        inner = self._card(parent)
        box = self._text(inner, 16)
        lines = []
        for tag, sug in RUNE_BY_TAG.items():
            lines.append(
                f"{tag}: {sug['primary']} — {sug['keystone']}\n"
                f"  Secundária: {sug['secondary']}\n"
                f"  {sug['note']}\n"
            )
        try:
            from data.scraper import format_rune_trees
            trees = format_rune_trees()
            if trees:
                lines.append("Árvores oficiais:\n" + trees)
        except Exception:
            pass
        self._set(box, "\n".join(lines))
        self._freeze_text(box)

    def _build_lane(self, parent: tk.Frame) -> None:
        inner = self._card(parent)
        box = self._text(inner, 18)
        lines = []
        for item in LANE_MACRO:
            lines.append(f"• {item['title']}: {item['body']}")
        lines.append("")
        for item in WAVE_TIPS:
            lines.append(f"• {item['title']}: {item['body']}")
        self._set(box, "\n".join(lines))
        self._freeze_text(box)

    # ── canais ─────────────────────────────────────────
    def _build_channels(self, parent: tk.Frame) -> None:
        C = self.colors
        inner = self._card(parent)

        wrap = tk.Frame(inner, bg=C["panel"])
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=C["panel"], highlightthickness=0)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner_list = tk.Frame(canvas, bg=C["panel"])
        inner_list.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner_list, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        store = load_store()
        overrides = store.get("channel_overrides") or {}
        self._channel_vars: dict[str, tk.StringVar] = {}
        labels = list(CHANNEL_LABELS.values())
        reverse = {v: k for k, v in CHANNEL_LABELS.items()}

        for alert_type, title in EDITABLE_ALERT_TYPES:
            row = tk.Frame(inner_list, bg=C["panel"])
            row.pack(fill="x", pady=4)
            tk.Label(
                row, text=title, font=self.ui.f_body,
                fg=C["text"], bg=C["panel"], width=36, anchor="w",
            ).pack(side="left")
            current = overrides.get(alert_type) or DEFAULT_CHANNELS.get(alert_type, "voice")
            var = tk.StringVar(value=CHANNEL_LABELS.get(current, "Voz"))
            self._channel_vars[alert_type] = var
            ttk.Combobox(
                row, textvariable=var, values=labels,
                state="readonly", style="App.TCombobox", width=16,
            ).pack(side="left")

        def save_channels():
            for alert_type, var in self._channel_vars.items():
                channel = reverse.get(var.get(), "text")
                set_channel_override(alert_type, channel)
            save_store()
            messagebox.showinfo("Avisos", "Canais salvos.")

        self.ui._btn(inner, "Salvar", save_channels, kind="primary").pack(
            anchor="w", pady=(12, 0),
        )

