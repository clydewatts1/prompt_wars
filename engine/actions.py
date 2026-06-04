"""
engine/actions.py
Action resolver — mutates board state for each bot action.
All Phase 1 actions resolve instantly and update board immediately.
"""

from engine.board import Board, Terrain, Structure, Wreckage, STRUCTURE_DEFINITIONS
from engine.bot import Bot

LASER_RANGE  = 2
LASER_DAMAGE = 20
EAT_FOOD_AMOUNT = 15


class ActionResolver:

    def __init__(self, board: Board):
        self.board = board

    def resolve(self, bot: Bot, action: dict, destruction_log: list,
                all_bots: list, cycle: int, destruction_counter: list) -> int:
        """
        Resolve action. Returns compute cost actually deducted.
        destruction_counter is a mutable [int] for tracking destruction order.
        """
        act = action["action"]

        if act == "next":
            return self._resolve_next(bot)

        elif act == "move":
            return self._resolve_move(bot, action)

        elif act == "eat":
            return self._resolve_eat(bot)

        elif act == "capture":
            return self._resolve_capture(bot)

        elif act == "attack":
            return self._resolve_attack(bot, action, all_bots, cycle,
                                         destruction_log, destruction_counter)

        elif act == "build":
            return self._resolve_build(bot, action)

        return 0

    # ── next ───────────────────────────────────────────────────────────────────

    def _resolve_next(self, bot: Bot) -> int:
        return 0

    # ── move ───────────────────────────────────────────────────────────────────

    def _resolve_move(self, bot: Bot, action: dict) -> int:
        direction = action["direction"]
        nq, nr = self.board.neighbour(bot.q, bot.r, direction)
        target = self.board.get_cell(nq, nr)
        cost = target.move_cost

        # Vacate current cell
        current = self.board.get_cell(bot.q, bot.r)
        if current:
            current.occupant_id = None

        # Move bot
        bot.q, bot.r = nq, nr
        target.occupant_id = bot.bot_id
        bot.deduct_compute(cost)
        return cost

    # ── eat ────────────────────────────────────────────────────────────────────

    def _resolve_eat(self, bot: Bot) -> int:
        cost = 1
        cell = self.board.get_cell(bot.q, bot.r)

        # Wreckage takes priority — more valuable
        if cell.wreckage:
            available = cell.wreckage.salvage_compute
            space = bot.max_compute - bot.compute_units
            absorbed = min(available, space)
            bot.add_compute(absorbed)
            cell.wreckage.salvage_compute -= absorbed
            if cell.wreckage.salvage_compute <= 0:
                cell.wreckage = None

        elif cell.current_food > 0:
            amount = min(EAT_FOOD_AMOUNT, cell.current_food)
            cell.current_food -= amount
            bot.add_compute(amount)

        bot.deduct_compute(cost)
        return cost

    # ── capture ────────────────────────────────────────────────────────────────

    def _resolve_capture(self, bot: Bot) -> int:
        cost = 3
        cell = self.board.get_cell(bot.q, bot.r)

        if cell.owner == bot.team:
            # Already owned — no-op but cost still deducted
            bot.deduct_compute(cost)
            return cost

        # Advance capture progress
        cell.capture_progress += 50.0

        if cell.capture_progress >= 100.0:
            cell.owner = bot.team
            cell.capture_progress = 100.0

        bot.deduct_compute(cost)
        return cost

    # ── attack ─────────────────────────────────────────────────────────────────

    def _resolve_attack(self, bot: Bot, action: dict, all_bots: list,
                         cycle: int, destruction_log: list,
                         destruction_counter: list) -> int:
        cost = 5
        direction = action["direction"]
        dq, dr = self._direction_vector(direction)

        q, r = bot.q, bot.r
        bot.deduct_compute(cost)

        for _ in range(LASER_RANGE):
            q += dq
            r += dr

            if not self.board.is_valid(q, r):
                break

            cell = self.board.get_cell(q, r)
            if not cell:
                break

            # Hit a structure first
            if cell.structure:
                cell.structure.hp -= LASER_DAMAGE
                if cell.structure.hp <= 0:
                    # Structure destroyed — leave wreckage
                    cell.wreckage = Wreckage(
                        source_bot_id=cell.structure.owner_id,
                        source_bot_name="structure",
                        created_cycle=cycle,
                        salvage_compute=10,
                    )
                    cell.structure = None
                # Barricade absorbs laser — stop
                break

            # Hit a bot
            target_bot = next((b for b in all_bots
                                if b.is_alive and b.q == q and b.r == r), None)
            if target_bot:
                target_bot.take_damage(LASER_DAMAGE)
                if target_bot.hp <= 0:
                    destruction_counter[0] += 1
                    target_bot.die(
                        cycle=cycle,
                        destroyed_by=bot.bot_id,
                        cause="laser_attack",
                        destruction_order=destruction_counter[0],
                    )
                    # Vacate cell, spawn wreckage
                    cell.occupant_id = None
                    cell.wreckage = Wreckage(
                        source_bot_id=target_bot.bot_id,
                        source_bot_name=target_bot.name,
                        created_cycle=cycle,
                        salvage_compute=target_bot.salvage_compute(),
                    )
                    destruction_log.append(target_bot.death_record())
                break

            # Asteroid blocks silently
            if cell.terrain == Terrain.ASTEROID:
                break

        return cost

    # ── build ──────────────────────────────────────────────────────────────────

    def _resolve_build(self, bot: Bot, action: dict) -> int:
        cost = 8
        direction = action["direction"]
        structure_type = action["target_structure"]
        nq, nr = self.board.neighbour(bot.q, bot.r, direction)
        target = self.board.get_cell(nq, nr)

        defn = STRUCTURE_DEFINITIONS[structure_type]
        target.structure = Structure(
            type=structure_type,
            hp=defn["hp"],
            max_hp=defn["max_hp"],
            owner_id=bot.bot_id,
            passable=defn["passable"],
        )
        bot.deduct_compute(cost)
        return cost

    # ── helpers ────────────────────────────────────────────────────────────────

    def _direction_vector(self, direction: str):
        from engine.board import DIRECTIONS
        return DIRECTIONS[direction]
