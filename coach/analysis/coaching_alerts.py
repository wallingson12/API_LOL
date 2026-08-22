from config import NUM_ADVANTAGE_MIN_DIFF
from game.events import parse_role, _has_smite
from analysis.analyzer import get_my_team_and_enemies
from core.players import find_player, kill_name_matches, player_name, cache_keys

_role_cache: dict[str, str] = {}
_advantage_state: tuple[int, int] | None = None


def reset_coaching_state():
    global _advantage_state
    _role_cache.clear()
    _advantage_state = None


def update_role_cache(all_players: list[dict]) -> None:
    for player in all_players:
        role = parse_role(player)
        if not role:
            continue
        for key in cache_keys(player):
            _role_cache[key] = role


def _resolve_role(victim: dict, kill_name: str, enemies: list[dict]) -> str | None:
    role = parse_role(victim)
    if role:
        return role

    for key in cache_keys(victim):
        if key in _role_cache:
            return _role_cache[key]

    if _has_smite(victim):
        return "jungler"

    for enemy in enemies:
        if kill_name_matches(kill_name, enemy) and _has_smite(enemy):
            return "jungler"

    return None


def _count_alive(players: list[dict]) -> int:
    return sum(1 for p in players if not p.get("isDead"))


def _num_advantage_alert(
    allies_alive: int,
    enemies_alive: int,
    game_time: float,
    objectives: list[str],
    enemy_inhib_destroyed: bool,
) -> dict | None:
    global _advantage_state

    diff = allies_alive - enemies_alive
    if diff < NUM_ADVANTAGE_MIN_DIFF or allies_alive < 1:
        if diff < NUM_ADVANTAGE_MIN_DIFF:
            _advantage_state = None
        return None

    state = (allies_alive, enemies_alive)
    if state == _advantage_state:
        return None
    _advantage_state = state

    return {
        "type": "num_advantage",
        "allies_alive": allies_alive,
        "enemies_alive": enemies_alive,
        "diff": diff,
        "game_time": game_time,
        "objectives": objectives,
        "enemy_inhib_destroyed": enemy_inhib_destroyed,
    }


def coaching_alerts_from_events(
    game_data: dict,
    events: list[dict],
    objective_tracker=None,
    *,
    enemy_inhib_destroyed: bool = False,
) -> list[dict]:
    alerts = []
    me, allies, enemies = get_my_team_and_enemies(game_data)
    if not me:
        return alerts

    all_players = game_data.get("allPlayers", [])
    update_role_cache(all_players)

    my_team_id = me.get("team")
    team = [me, *allies]
    i_am_jungler = parse_role(me) == "jungler"

    for ev in events:
        if ev.get("type") != "kill":
            continue

        kill_name = ev.get("victim", "")
        victim = find_player(all_players, kill_name)
        if not victim or victim.get("team") == my_team_id:
            continue

        role = _resolve_role(victim, kill_name, enemies)
        victim_name = player_name(victim)

        allies_alive = _count_alive(team)
        enemies_alive = _count_alive(enemies)
        objectives = (
            objective_tracker.available_objectives(game_data)
            if objective_tracker
            else []
        )
        game_time = float(game_data.get("gameData", {}).get("gameTime", 0) or 0)
        advantage = _num_advantage_alert(
            allies_alive, enemies_alive, game_time, objectives, enemy_inhib_destroyed,
        )
        if advantage:
            alerts.append(advantage)
            continue

        if role == "jungler":
            alerts.append({
                "type": "enemy_jg_dead_gank",
                "victim": victim_name,
                "is_jungler": i_am_jungler,
            })

    return alerts
