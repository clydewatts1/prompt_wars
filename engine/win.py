"""
engine/win.py
Termination trigger checker.
The engine determines WHEN the game ends.
The Overlord determines WHO won and WHY.
"""

from engine.bot import Bot


class WinChecker:

    def __init__(self, turn_limit: int):
        self.turn_limit = turn_limit

    def check(self, bots: list, cycle: int, destruction_log: list) -> dict:
        """
        Check all termination conditions.
        Returns result dict. game_over=False means continue.
        """
        alive = [b for b in bots if b.is_alive]

        # All bots destroyed
        if len(alive) == 0:
            return {
                "game_over": True,
                "termination_reason": "all_bots_destroyed",
                "cycle": cycle,
                "survivors": [],
                "destruction_log": destruction_log,
            }

        # Single survivor
        if len(alive) == 1:
            return {
                "game_over": True,
                "termination_reason": "single_survivor",
                "cycle": cycle,
                "survivors": [alive[0].serialize()],
                "destruction_log": destruction_log,
            }

        # Turn limit reached
        if cycle >= self.turn_limit:
            return {
                "game_over": True,
                "termination_reason": "turn_limit_reached",
                "cycle": cycle,
                "survivors": [b.serialize() for b in alive],
                "destruction_log": destruction_log,
            }

        return {
            "game_over": False,
            "termination_reason": None,
            "cycle": cycle,
            "survivors": [b.serialize() for b in alive],
        }
