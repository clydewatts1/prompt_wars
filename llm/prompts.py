"""
llm/prompts.py
Builds the JSON payloads sent to the LLM each turn.
Handshake sent once on Turn 0. Turn request sent every cycle.
"""

from engine.board import Board
from engine.bot import Bot

PROTOCOL_VERSION = "1.7"


def build_handshake(config: dict) -> dict:
    """Static rules payload sent as system context on Turn 0."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "game_title": "Prompt Wars",
        "ruleset": {
            "vitality_name": "HP",
            "energy_name": "Compute Units",
            "turn_costs": {
                "next_action": 0,
                "move_ground": 2,
                "move_forest": 4,
                "eat_action": 1,
                "capture_action": 3,
                "peek_action": 1,
                "attack_laser": 5,
                "build_action": 8,
                "push_action": "variable (energy)",
                "kick_action": 3,
            },
            "weapon_parameters": {
                "range": 2,
                "base_damage": 20,
            },
            "memory_limit_characters": config["rules"]["memory_max_characters"],
            "buildable_structures": [
                {
                    "name": "barricade",
                    "description": "Impassable obstacle. Blocks movement and lasers. HP: 50.",
                    "placement": "adjacent",
                },
                {
                    "name": "collector",
                    "description": "Must be placed on Grass or Forest. Generates +5 CU per cycle. HP: 20.",
                    "placement": "adjacent",
                },
            ],
        },
        "movement_vocabulary": [
            "east", "south_east", "south_west", "west", "north_west", "north_east"
        ],
        "response_schema": {
            "thought": "string — your reasoning this turn",
            "action": "string — one of the valid action commands (move, eat, capture, peek, attack, build, push, kick)",
            "direction": "string — required for move, attack, peek, build, push, kick",
            "target_structure": "string — required for build: barricade or collector",
            "save_memory": f"string — your memory for next turn, max {config['rules']['memory_max_characters']} characters",
        }
    }


def build_turn_request(bot: Bot, board: Board, cycle: int,
                        rules: dict) -> dict:
    """Full telemetry payload sent as user message each cycle."""
    cell = board.get_cell(bot.q, bot.r)
    memory_len = len(bot.memory_string)
    max_chars = rules["memory_max_characters"]

    return {
        "protocol_version": PROTOCOL_VERSION,
        "cycle_id": cycle,
        "bot_identity": {
            "id": bot.bot_id,
            "name": bot.name,
            "team": bot.team,
        },
        "status": {
            "hp": bot.hp,
            "max_hp": bot.max_hp,
            "compute_units": bot.compute_units,
            "max_compute": bot.max_compute,
            "starvation_warning": bot.starvation_warning(
                rules["starvation_warning_threshold"]
            ),
            "starvation_threshold": rules["starvation_warning_threshold"],
        },
        "current_cell": _serialize_current_cell(cell),
        "spatial_telemetry": {
            "distance_to_edge": board.distance_to_edge(bot.q, bot.r),
        },
        "memory_constraints": {
            "max_characters": max_chars,
            "current_memory_length": memory_len,
            "characters_remaining": max_chars - memory_len,
        },
        "memory_in": bot.memory_string,
        "last_turn_result": bot.last_turn_result,
        "passive_sensor_radar": _build_passive_radar(bot, board),
        "peek_result": bot.pending_peek_result,
    }


def _serialize_current_cell(cell) -> dict:
    if not cell:
        return {}
    return {
        "terrain": cell.terrain.value,
        "food": cell.current_food,
        "max_food": cell.max_food,
        "owner": cell.owner,
        "capture_progress": cell.capture_progress,
        "structure": cell.structure.serialize() if cell.structure else None,
        "wreckage": cell.wreckage.serialize() if cell.wreckage else None,
        "occupant_id": cell.occupant_id,
        "rock": cell.rock,
        "ball": cell.ball,
        "goal": cell.goal,
    }


def _build_passive_radar(bot: Bot, board: Board) -> list:
    """
    Passive radar — free sweep of all adjacent cells (distance 1).
    Reports entity type, structure, wreckage, occupant for each neighbour.
    """
    from engine.board import DIRECTIONS, Terrain
    radar = []
    for direction, (dq, dr) in DIRECTIONS.items():
        nq, nr = bot.q + dq, bot.r + dr
        if not board.is_valid(nq, nr):
            continue
        cell = board.get_cell(nq, nr)
        if not cell:
            continue

        entry = {
            "direction": direction,
            "entity_type": cell.terrain.value,
            "coordinate": {"q": nq, "r": nr},
            "current_food": cell.current_food,
            "structure": cell.structure.serialize() if cell.structure else None,
            "wreckage": cell.wreckage.serialize() if cell.wreckage else None,
            "occupant_id": cell.occupant_id,
            "rock": cell.rock,
            "ball": cell.ball,
            "goal": cell.goal,
        }
        radar.append(entry)
    return radar
