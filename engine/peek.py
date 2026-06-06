"""
engine/peek.py
Peek raycasting — deferred Phase 2 resolution.
Rays fire against the final settled board state after all bots have acted.
"""

from engine.board import Board, Terrain, DIRECTIONS
from engine.bot import Bot

PEEK_RANGE = 3


class PeekResolver:

    def __init__(self, board: Board):
        self.board = board

    def resolve(self, bot: Bot, action: dict, all_bots: list,
                issued_cycle: int) -> dict:
        """
        Fire raycast from bot position in action direction.
        Returns full peek_result dict for delivery next cycle.
        """
        direction = action["direction"]
        dq, dr = DIRECTIONS[direction]
        cells_scanned = []

        q, r = bot.q, bot.r

        for dist in range(1, PEEK_RANGE + 1):
            q += dq
            r += dr

            # Out of bounds — stop silently
            if not self.board.is_valid(q, r):
                break

            cell = self.board.get_cell(q, r)
            if not cell:
                break

            # Asteroid — stop silently, not reported
            if cell.terrain == Terrain.ASTEROID:
                break

            # Build cell report
            occupant = self._find_occupant(q, r, all_bots)
            cell_report = {
                "distance": dist,
                "coordinate": {"q": q, "r": r},
                "terrain": cell.terrain.value,
                "current_food": cell.current_food,
                "max_food": cell.max_food,
                "structure": cell.structure.serialize() if cell.structure else None,
                "wreckage": cell.wreckage.serialize() if cell.wreckage else None,
                "occupant": self._serialize_occupant(occupant) if occupant else None,
                "rock": cell.rock,
                "ball": cell.ball,
                "goal": cell.goal,
                "ray_blocked_here": False,
            }

            # Barricade — report then stop
            if cell.structure and cell.structure.type == "barricade":
                cell_report["ray_blocked_here"] = True
                cells_scanned.append(cell_report)
                break

            # Bot — report then stop
            if occupant:
                cell_report["ray_blocked_here"] = True
                cells_scanned.append(cell_report)
                break

            cells_scanned.append(cell_report)

        return {
            "direction": direction,
            "issued_cycle": issued_cycle,
            "resolved_at": f"end_of_cycle_{issued_cycle}",
            "delivered_cycle": issued_cycle + 1,
            "compute_spent": 1,
            "cells_scanned": cells_scanned,
        }

    def _find_occupant(self, q: int, r: int, all_bots: list):
        return next(
            (b for b in all_bots if b.is_alive and b.q == q and b.r == r),
            None
        )

    def _serialize_occupant(self, bot: Bot) -> dict:
        return {
            "bot_id": bot.bot_id,
            "name": bot.name,
            "team": bot.team,
            "hp": bot.hp,
            "max_hp": bot.max_hp,
        }
