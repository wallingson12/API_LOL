"""Motor principal do coach — controlado pela interface desktop."""

import threading
import time
import traceback

from app_state import STATE
from config import (
    MAP_REMINDER_INTERVAL_SECONDS,
    POLL_INTERVAL_MENU_SECONDS,
    POLL_INTERVAL_SECONDS,
    RESPAWN_ALERT_COOLDOWN_SECONDS,
)
from api.live_client import get_game_data
from api.lcu_client import (
    get_champ_select_session,
    get_gameflow_phase,
    parse_champ_select_context,
)
from analysis.analyzer import get_my_team_and_enemies, reset_analyzer_state
from analysis.coaching_alerts import reset_coaching_state
from analysis.build_suggest import BuildSuggestTracker, current_suggestion
from analysis.enemy_item_board import EnemyItemAlertTracker, build_enemy_item_board
from analysis.hud_cards import build_hud_cards
from analysis.jungle_reminders import JungleReminderTracker
from analysis.my_deaths import MyDeathTracker
from analysis.objective_spawns import ObjectiveSpawnTracker
from analysis.pregame_briefing import build_ingame_briefing_lines, build_pregame_lines
from analysis.resource_alerts import ResourceAlertTracker
from analysis.role_resolve import resolve_lane_opponent, resolve_my_role
from analysis.tower_lane import TowerLaneTracker
from analysis.ward_tracker import WardTracker
from alerts.pipeline import collect_ingame_alerts, dispatch_alerts
from alerts.priority import event_speech_priority
from data.champion_data import load_champions
from data.item_data import load_items
from game.events import GameEventTracker
from game.player_match import active_player_name
from voice.narrator import narrate_event, narrate_respawn
from voice.voice import VoiceCoach

_keep_range_started = False
_vision_started = False
_last_briefing_keys: set[str] = set()
_lcu_lane_ctx: dict = {}
_briefed_match_key: str | None = None
_in_champ_select = False


def _ensure_keep_range() -> None:
    global _keep_range_started
    if _keep_range_started:
        return
    try:
        from keep_range import ativar_range
        threading.Thread(target=ativar_range, daemon=True).start()
        _keep_range_started = True
        STATE.update(keep_range_enabled=True)
    except Exception:
        pass


def _ensure_vision() -> None:
    """Liga o rastreador visual (print + modelo) junto com o coach."""
    global _vision_started
    if _vision_started:
        return
    try:
        from vision.detect import start_tracker
        start_tracker()
        _vision_started = True
        STATE.update(vision_enabled=True)
        STATE.log("Rastreador visual ligado.")
    except Exception as exc:
        STATE.log(f"Rastreador visual indisponível: {exc}")


def _match_key(game_data: dict, my_champ: str | None) -> str:
    """Identifica a partida atual (evita briefing repetido no mesmo jogo)."""
    gd = game_data.get("gameData") or {}
    start = gd.get("gameStartTime") or gd.get("gameId") or ""
    mode = gd.get("gameMode") or ""
    return f"{start}|{mode}|{my_champ or ''}"


def _empty_item_board() -> dict:
    return {
        "cura": [],
        "vampirismo": [],
        "escudo": [],
        "resistencia_magica": [],
        "corta_cura": [],
    }


def _finish_game(voice: VoiceCoach | None = None) -> None:
    """Pós-partida: limpa estado. Sem resumo/voz — itens já avisados na hora."""
    global _lcu_lane_ctx
    _lcu_lane_ctx = {}
    reset_analyzer_state()
    reset_coaching_state()

    STATE.update(
        status="post_game",
        status_label="Partida encerrada",
        game_time=0.0,
        my_champion="",
        my_role="",
        opponent_champion="",
        dragon_us=0,
        dragon_them=0,
        elder_phase=False,
        last_dragon_key="",
        enemy_item_board=_empty_item_board(),
        build_suggestion="",
        hud_cards=[],
    )
    STATE.clear_hud()


def _reset_after_game() -> None:
    _finish_game()


class LoggingVoiceCoach(VoiceCoach):
    """Loga na UI só quando a fala passa no cooldown (não some alerta fantasma)."""

    def say(self, text: str, alert_key=None, cooldown=15, priority=0):
        now = time.time()
        if alert_key:
            last = self._last_spoken.get(alert_key, 0)
            if now - last < cooldown:
                return
            self._last_spoken[alert_key] = now

        STATE.log(text)
        # cooldown já aplicado — não deixa o pai bloquear de novo
        super().say(text, alert_key=None, cooldown=0, priority=priority)


class CoachEngine:
    def __init__(self):
        self._voice: LoggingVoiceCoach | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._run_id = 0
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def preload(self) -> None:
        """Carrega dados sem iniciar o coach (para análise na UI)."""
        _ensure_keep_range()
        if STATE.data_loaded:
            return
        STATE.update(status_label="Carregando dados...")
        try:
            load_champions()
            load_items()
            try:
                from data.scraper import fetch_runes
                fetch_runes(force=False)
            except Exception:
                pass
        except Exception as exc:
            STATE.log(f"Falha ao carregar dados: {exc}")
        STATE.update(data_loaded=True, status_label="Coach parado")

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive() and self._running:
                return False
            self._run_id += 1
            run_id = self._run_id
            self._running = True
            self._thread = threading.Thread(
                target=self._run,
                args=(run_id,),
                daemon=True,
                name=f"CoachEngine-{run_id}",
            )
            thread = self._thread
        STATE.update(coach_running=True, status="idle", status_label="Iniciando coach...")
        STATE.log("Coach iniciado.")
        thread.start()
        _ensure_vision()
        return True

    def stop(self) -> None:
        with self._lock:
            self._running = False
        STATE.update(
            coach_running=False,
            status="stopped",
            status_label="Coach parado",
            game_time=0.0,
            my_champion="",
            my_role="",
            opponent_champion="",
            dragon_us=0,
            dragon_them=0,
            elder_phase=False,
            last_dragon_key="",
            enemy_item_board=_empty_item_board(),
            build_suggestion="",
            hud_cards=[],
            vision_champion="",
            vision_confidence=0.0,
        )
        STATE.clear_hud()
        STATE.log("Coach parado.")

    def set_voice_enabled(self, enabled: bool) -> None:
        STATE.update(voice_enabled=enabled)
        if self._voice:
            self._voice.set_muted(not enabled)

    def speak(self, text: str) -> None:
        if not text:
            return
        if self._voice is None:
            try:
                self._voice = LoggingVoiceCoach()
            except Exception:
                STATE.log(text)
                return
        self._voice.say(text, alert_key=None, cooldown=0, priority=100)

    def enable_keep_range(self) -> None:
        _ensure_keep_range()

    def _still_this_run(self, run_id: int) -> bool:
        with self._lock:
            return self._running and self._run_id == run_id

    def _init_voice(self) -> None:
        """Inicia TTS sem travar o coach se o áudio falhar."""
        try:
            if self._voice is None:
                self._voice = LoggingVoiceCoach()
            self._voice.set_muted(False)
            STATE.update(voice_enabled=True)
            # Não espera a fila esvaziar — só enfileira o teste
            self._voice.say("Coach de voz pronto.", alert_key=None, cooldown=0)
        except Exception as exc:
            STATE.log(f"Voz indisponível: {exc}")
            traceback.print_exc()

    def _run(self, run_id: int) -> None:
        try:
            self.preload()
            if not self._still_this_run(run_id):
                return
            self._init_voice()
            if not self._still_this_run(run_id):
                return

            STATE.update(status="idle", status_label="Aguardando partida (Live Client off)")

            while self._still_this_run(run_id):
                try:
                    game_data = get_game_data()
                    if game_data is not None:
                        self._ingame_loop(run_id)
                    else:
                        self._pregame_briefing()
                except Exception as exc:
                    STATE.log(f"Erro no coach: {exc}")
                    traceback.print_exc()
                time.sleep(POLL_INTERVAL_MENU_SECONDS)
        except Exception as exc:
            STATE.log(f"Erro fatal no coach: {exc}")
            traceback.print_exc()
        finally:
            with self._lock:
                # Só esta geração pode marcar parado (evita matar um start novo)
                if self._run_id == run_id:
                    self._running = False
                    if STATE.coach_running:
                        STATE.update(
                            coach_running=False,
                            status="stopped",
                            status_label="Coach parado",
                        )

    def _pregame_briefing(self) -> None:
        global _last_briefing_keys, _lcu_lane_ctx, _briefed_match_key, _in_champ_select

        if not self._running:
            return

        phase = get_gameflow_phase()
        if phase != "ChampSelect":
            if STATE.status == "champ_select":
                STATE.update(status="idle", status_label="Aguardando partida (Live Client off)")
            _in_champ_select = False
            return

        if not _in_champ_select:
            _in_champ_select = True
            _last_briefing_keys.clear()
            _briefed_match_key = None

        STATE.update(status="champ_select", status_label="Seleção de campeões")

        session = get_champ_select_session()
        if not session:
            return

        ctx = parse_champ_select_context(session)
        if ctx.get("my_position"):
            _lcu_lane_ctx = {
                "my_position": ctx["my_position"],
                "lane_opponent_name": ctx.get("lane_opponent_name"),
            }

        lines = build_pregame_lines(ctx)
        if not lines or not self._voice:
            return

        opp = ctx.get("lane_opponent_name")
        if opp:
            speak_key = f"pregame_vs_{opp}"
            if speak_key not in _last_briefing_keys:
                self._voice.say(f"Vs {opp}.", alert_key=speak_key, cooldown=300)
                _last_briefing_keys.add(speak_key)

        for text, key in lines:
            if key in _last_briefing_keys:
                continue
            STATE.push_hud(text, kind="warn", key=key, cooldown=300)
            _last_briefing_keys.add(key)

    def _ingame_loop(self, run_id: int) -> None:
        global _last_briefing_keys, _lcu_lane_ctx, _briefed_match_key

        if not self._voice:
            self._init_voice()
        voice = self._voice
        if not voice:
            STATE.log("Sem voz — alertas só no log.")
            return

        tracker = GameEventTracker()
        my_deaths = MyDeathTracker()
        tower_lane = TowerLaneTracker()
        ward_tracker = WardTracker()
        jungle_reminders = JungleReminderTracker()
        objective_spawns = ObjectiveSpawnTracker()
        enemy_items = EnemyItemAlertTracker()
        build_suggest = BuildSuggestTracker()
        resource_alerts = ResourceAlertTracker()
        last_map_reminder_game_time: float | None = None
        api_misses = 0
        warned_no_player = False
        ingame_briefing_done = False
        greeted = False

        STATE.update(status="in_game", status_label="Em partida")

        while self._still_this_run(run_id):
            loop_start = time.monotonic()
            game_data = get_game_data()
            if game_data is None:
                api_misses += 1
                if api_misses >= 120:
                    _finish_game()
                    break
                STATE.update(status_label="Em partida (API instável…)")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue
            api_misses = 0

            my_name = active_player_name(game_data) or "?"
            me, _, enemies = get_my_team_and_enemies(game_data)
            my_role = resolve_my_role(me if me else None, _lcu_lane_ctx.get("my_position"))
            my_team = me.get("team") if me else None
            my_champ = (me or {}).get("championName", "")
            game_time = float(game_data.get("gameData", {}).get("gameTime", 0) or 0)
            match_key = _match_key(game_data, my_champ)

            game_mode = str((game_data.get("gameData") or {}).get("gameMode") or "")
            mode_label = {
                "CLASSIC": "SR",
                "SWIFTPLAY": "Swiftplay",
                "ARAM": "ARAM",
                "URF": "URF",
            }.get(game_mode, game_mode or "partida")

            if not greeted:
                greeted = True
                voice.say(
                    "Coach conectado.",
                    alert_key=f"game_start_{match_key}",
                    cooldown=999999,
                    priority=event_speech_priority("game_start"),
                )

            try:
                dragon_us, dragon_them = objective_spawns.dragon_score(my_team)
            except Exception:
                dragon_us, dragon_them = 0, 0
            try:
                item_board = build_enemy_item_board(game_data)
            except Exception:
                item_board = _empty_item_board()
                traceback.print_exc()

            try:
                sug = current_suggestion(item_board, me if me else None, enemies)
                sug_ui = (sug or {}).get("ui") or ""
            except Exception:
                sug_ui = ""
                traceback.print_exc()

            try:
                objective_spawns.observe_events([], game_data)
            except Exception:
                traceback.print_exc()

            lane_enemy = resolve_lane_opponent(
                enemies, my_role, _lcu_lane_ctx.get("lane_opponent_name"),
            )
            opp_champ = (lane_enemy or {}).get("championName") or ""
            try:
                dragon_key = objective_spawns.last_dragon_key() or ""
            except Exception:
                dragon_key = ""
            try:
                ward_hud = ward_tracker.hud_snapshot(game_data, my_name)
            except Exception:
                ward_hud = None
            try:
                cards = build_hud_cards(
                    my_role=my_role,
                    my_champion=my_champ,
                    opponent_name=opp_champ or None,
                    dragon_key=dragon_key or None,
                    elder_phase=getattr(objective_spawns, "elder_phase", False),
                    ward_hud=ward_hud,
                )
            except Exception:
                cards = []
                traceback.print_exc()

            STATE.update(
                game_time=game_time,
                my_champion=my_champ,
                my_role=my_role or "",
                opponent_champion=opp_champ,
                dragon_us=dragon_us,
                dragon_them=dragon_them,
                elder_phase=getattr(objective_spawns, "elder_phase", False),
                last_dragon_key=dragon_key,
                enemy_item_board=item_board,
                build_suggestion=sug_ui,
                hud_cards=cards,
                status_label=f"Em partida · {mode_label}",
            )

            if not me and not warned_no_player:
                warned_no_player = True
                STATE.log(f"Jogador não encontrado (API: {my_name}).")

            if (
                not ingame_briefing_done
                and me
                and enemies
                and match_key != _briefed_match_key
            ):
                ingame_briefing_done = True
                _briefed_match_key = match_key
                lcu_pos = _lcu_lane_ctx.get("my_position") or my_role or "?"
                for text, key in build_ingame_briefing_lines(
                    lcu_pos, my_champ, opp_champ, my_ingame_role=my_role,
                ):
                    if key in _last_briefing_keys:
                        continue
                    STATE.push_hud(text, kind="warn", key=key, cooldown=9999)
                    _last_briefing_keys.add(key)
                if opp_champ:
                    voice.say(
                        f"Vs {opp_champ}.",
                        alert_key=f"vs_{opp_champ}_{match_key}",
                        cooldown=999999,
                    )

            try:
                new_events = tracker.diff(game_data)
                objective_spawns.observe_events(new_events, game_data)
                ward_tracker.observe_events(new_events, game_data, my_name)

                for ev in new_events:
                    if ev.get("type") == "game_end":
                        _finish_game()
                        return
                    if ev.get("type") == "player_respawned":
                        respawn = narrate_respawn(ev, my_role)
                        if respawn:
                            text, key = respawn
                            voice.say(
                                text,
                                alert_key=key,
                                cooldown=RESPAWN_ALERT_COOLDOWN_SECONDS,
                                priority=event_speech_priority("player_respawned"),
                            )
                        continue
                    text = narrate_event(ev, my_name, my_team, game_data.get("allPlayers"))
                    if text:
                        voice.say(text, priority=event_speech_priority(ev.get("type", "")))

                extra = []
                try:
                    extra.extend(resource_alerts.update(game_data))
                except Exception:
                    traceback.print_exc()
                alerts = collect_ingame_alerts(
                    game_data=game_data,
                    new_events=new_events,
                    my_name=my_name,
                    my_team=my_team,
                    my_role=my_role,
                    lcu_lane_ctx=_lcu_lane_ctx,
                    jungle_reminders=jungle_reminders,
                    objective_spawns=objective_spawns,
                    my_deaths=my_deaths,
                    tower_lane=tower_lane,
                    ward_tracker=ward_tracker,
                    tracker_is_live=tracker.is_game_live(),
                    monotonic_now=time.monotonic(),
                    extra_alerts=extra,
                )
                try:
                    alerts.extend(enemy_items.alerts_from_board(item_board))
                    alerts.extend(build_suggest.alerts(item_board, me if me else None, enemies))
                except Exception:
                    traceback.print_exc()
                dispatch_alerts(voice, alerts)

                armed_at = tracker.map_reminder_armed_at()
                if armed_at is not None and my_role != "jungler":
                    if last_map_reminder_game_time is None:
                        last_map_reminder_game_time = armed_at
                    elif game_time >= last_map_reminder_game_time + MAP_REMINDER_INTERVAL_SECONDS:
                        last_map_reminder_game_time = game_time
                        STATE.push_hud(
                            "Olhe o mapa. Wave, jungle e lados.",
                            kind="info",
                            key="map_reminder",
                            cooldown=MAP_REMINDER_INTERVAL_SECONDS,
                        )
            except Exception as exc:
                STATE.log(f"Erro no loop: {exc}")
                traceback.print_exc()

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, POLL_INTERVAL_SECONDS - elapsed))

        tower_lane.reset()
        jungle_reminders.reset()
        ward_tracker.reset()
        objective_spawns.reset()
        resource_alerts.reset()
