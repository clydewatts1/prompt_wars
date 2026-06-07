"""
engine/validator.py
Validates LLM responses against JSON schema and board rules.
Returns structured result — never raises exceptions.
"""

import json
from engine.board import Board, DIRECTIONS
from engine.bot import Bot


VALID_ACTIONS = ["move", "eat", "attack", "peek", "build", "capture", "next", "push", "kick"]
VALID_DIRECTIONS = list(DIRECTIONS.keys())
VALID_STRUCTURES = ["barricade", "collector"]

# Compute costs per action (matches handshake schema)
ACTION_COSTS = {
    "next":    0,
    "move":    2,   # ground; forest checked separately
    "eat":     1,
    "capture": 3,
    "attack":  5,
    "peek":    1,
    "build":   8,
    "kick":    3,
}


class Validator:

    def __init__(self, rules: dict):
        self.memory_max = rules["memory_max_characters"]
        self.starvation_threshold = rules["starvation_warning_threshold"]

    # ── LLM response parsing ───────────────────────────────────────────────────

    def parse_response(self, raw: str) -> tuple:
        """
        Parse raw LLM string into action dict.
        Returns (action_dict, error_dict) — one will always be None.
        """
        if raw is None:
            return None, {"reason": "invalid_json", "compute_deducted": 0,
                          "action_attempted": None}

        # Clean markdown code blocks if present
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None, {"reason": "invalid_json", "compute_deducted": 0,
                          "action_attempted": None}

        # Required fields
        if not isinstance(data, dict):
            return None, {"reason": "invalid_json", "compute_deducted": 0,
                          "action_attempted": None}

        thought = data.get("thought", "")

        action = data.get("action")
        if action not in VALID_ACTIONS:
            return None, {"reason": "invalid_json", "compute_deducted": 0,
                          "action_attempted": None, "thought": thought}

        # Direction required for directional actions
        if action in ["move", "attack", "peek", "build", "push", "kick"]:
            if data.get("direction") not in VALID_DIRECTIONS:
                return None, {"reason": "invalid_json", "compute_deducted": 0,
                              "action_attempted": action, "thought": thought}

        # Build requires target_structure
        if action == "build":
            if data.get("target_structure") not in VALID_STRUCTURES:
                return None, {"reason": "invalid_json", "compute_deducted": 0,
                              "action_attempted": action, "thought": thought}

        # Push requires energy
        if action == "push":
            energy = data.get("energy")
            if not isinstance(energy, int) or energy < 1:
                return None, {"reason": "invalid_json", "compute_deducted": 0,
                              "action_attempted": action, "thought": thought}

        # Memory overflow check
        save_memory = data.get("save_memory")
        if save_memory is None:
            save_memory = ""
        elif not isinstance(save_memory, str):
            save_memory = str(save_memory)
        if len(save_memory) > self.memory_max:
            return None, {
                "reason": "memory_overflow",
                "compute_deducted": 0,
                "action_attempted": action,
                "characters_submitted": len(save_memory),
                "characters_allowed": self.memory_max,
                "attempted_save_memory": save_memory,
                "thought": thought,
            }

        return data, None

    # ── Board rule validation ──────────────────────────────────────────────────

    def validate_action(self, bot: Bot, action: dict, board: Board) -> tuple:
        """
        Validate a parsed action dict against current board state.
        Returns (valid: bool, error_dict or None)
        """
        act = action["action"]
        cost = self._get_cost(bot, action, board)

        # Compute check — all actions except next
        if act != "next" and bot.compute_units < cost:
            return False, {
                "reason": "illegal_action",
                "detail": "insufficient_compute",
                "compute_deducted": 0,
                "action_attempted": act,
            }

        if act == "move":
            return self._validate_move(bot, action, board, cost)

        if act == "attack":
            return self._validate_attack(bot, action, board, cost)

        if act == "build":
            return self._validate_build(bot, action, board, cost)

        if act == "eat":
            return self._validate_eat(bot, board, cost)

        if act == "capture":
            return self._validate_capture(bot, board, cost)

        if act == "push":
            return self._validate_push(bot, action, board, cost)

        if act == "kick":
            return self._validate_kick(bot, action, board, cost)

        # peek and next always valid if compute sufficient
        return True, None

    def _get_cost(self, bot: Bot, action: dict, board: Board) -> int:
        act = action["action"]
        if act == "push":
            return action.get("energy", 1)
        if act == "move":
            nq, nr = board.neighbour(bot.q, bot.r, action["direction"])
            target = board.get_cell(nq, nr)
            if target:
                return target.move_cost
        return ACTION_COSTS.get(act, 0)

    def _validate_move(self, bot: Bot, action: dict, board: Board, cost: int):
        direction = action["direction"]
        nq, nr = board.neighbour(bot.q, bot.r, direction)

        if not board.is_valid(nq, nr):
            return False, {"reason": "illegal_action", "detail": "out_of_bounds",
                           "compute_deducted": cost, "action_attempted": "move"}

        target = board.get_cell(nq, nr)
        if not target:
            return False, {"reason": "illegal_action", "detail": "out_of_bounds",
                           "compute_deducted": cost, "action_attempted": "move"}

        if not target.is_passable():
            return False, {"reason": "illegal_action", "detail": "cell_impassable",
                           "compute_deducted": cost, "action_attempted": "move"}

        if target.is_occupied():
            return False, {"reason": "illegal_action", "detail": "target_cell_occupied",
                           "compute_deducted": cost, "action_attempted": "move"}

        return True, None

    def _validate_attack(self, bot: Bot, action: dict, board: Board, cost: int):
        # Attack is always valid if bot has compute and direction is valid
        # (laser simply travels until it hits something or max range)
        return True, None

    def _validate_build(self, bot: Bot, action: dict, board: Board, cost: int):
        direction = action["direction"]
        structure_type = action["target_structure"]
        nq, nr = board.neighbour(bot.q, bot.r, direction)

        if not board.is_valid(nq, nr):
            return False, {"reason": "illegal_action", "detail": "out_of_bounds",
                           "compute_deducted": cost, "action_attempted": "build"}

        target = board.get_cell(nq, nr)
        if not target or not target.traversable:
            return False, {"reason": "illegal_action", "detail": "cell_impassable",
                           "compute_deducted": cost, "action_attempted": "build"}

        if target.is_occupied():
            return False, {"reason": "illegal_action", "detail": "target_cell_occupied",
                           "compute_deducted": cost, "action_attempted": "build"}

        if target.structure:
            return False, {"reason": "illegal_action", "detail": "structure_already_present",
                           "compute_deducted": cost, "action_attempted": "build"}

        # Collector must be on grass or forest
        if structure_type == "collector":
            from engine.board import Terrain
            if target.terrain not in [Terrain.GRASS, Terrain.FOREST]:
                return False, {"reason": "illegal_action", "detail": "collector_invalid_terrain",
                               "compute_deducted": cost, "action_attempted": "build"}

        return True, None

    def _validate_eat(self, bot: Bot, board: Board, cost: int):
        cell = board.get_cell(bot.q, bot.r)
        if not cell:
            return False, {"reason": "illegal_action", "detail": "no_cell",
                           "compute_deducted": cost, "action_attempted": "eat"}

        has_food = cell.current_food > 0
        has_wreckage = cell.wreckage is not None

        if not has_food and not has_wreckage:
            return False, {"reason": "illegal_action", "detail": "nothing_to_eat",
                           "compute_deducted": cost, "action_attempted": "eat"}

        return True, None

    def _validate_capture(self, bot: Bot, board: Board, cost: int):
        cell = board.get_cell(bot.q, bot.r)
        if not cell:
            return False, {"reason": "illegal_action", "detail": "no_cell",
                           "compute_deducted": cost, "action_attempted": "capture"}
        return True, None

    def _validate_push(self, bot: Bot, action: dict, board: Board, cost: int):
        direction = action["direction"]
        nq, nr = board.neighbour(bot.q, bot.r, direction)

        if not board.is_valid(nq, nr):
            return False, {"reason": "illegal_action", "detail": "out_of_bounds",
                           "compute_deducted": cost, "action_attempted": "push"}

        target = board.get_cell(nq, nr)
        if not target or not target.rock:
            return False, {"reason": "illegal_action", "detail": "no_rock_to_push",
                           "compute_deducted": cost, "action_attempted": "push"}

        return True, None

    def _validate_kick(self, bot: Bot, action: dict, board: Board, cost: int):
        direction = action["direction"]
        nq, nr = board.neighbour(bot.q, bot.r, direction)

        if not board.is_valid(nq, nr):
            return False, {"reason": "illegal_action", "detail": "out_of_bounds",
                           "compute_deducted": cost, "action_attempted": "kick"}

        target = board.get_cell(nq, nr)
        if not target or target.ball is None:
            return False, {"reason": "illegal_action", "detail": "no_ball_to_kick",
                           "compute_deducted": cost, "action_attempted": "kick"}

        return True, None
