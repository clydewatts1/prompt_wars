"""
engine/board.py
Hex grid board — axial coordinate system (q, r)
Invariant: q + r + s = 0  where s = -q - r
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from enum import Enum


# ── Direction vectors ──────────────────────────────────────────────────────────

DIRECTIONS = {
    "east":       ( 1,  0),
    "south_east": ( 0,  1),
    "south_west": (-1,  1),
    "west":       (-1,  0),
    "north_west": ( 0, -1),
    "north_east": ( 1, -1),
}

VALID_DIRECTIONS = list(DIRECTIONS.keys())


# ── Terrain ────────────────────────────────────────────────────────────────────

class Terrain(str, Enum):
    GROUND       = "ground"
    GRASS        = "grass"
    FOREST       = "forest"
    ASTEROID     = "asteroid"
    CONTROL_NODE = "control_node"


TERRAIN_PROPERTIES = {
    Terrain.GROUND:       {"traversable": True,  "max_food": 0,  "regen_rate": 0, "cover": 0.0,  "move_cost": 2},
    Terrain.GRASS:        {"traversable": True,  "max_food": 20, "regen_rate": 2, "cover": 0.1,  "move_cost": 2},
    Terrain.FOREST:       {"traversable": True,  "max_food": 50, "regen_rate": 1, "cover": 0.3,  "move_cost": 4},
    Terrain.ASTEROID:     {"traversable": False, "max_food": 0,  "regen_rate": 0, "cover": 1.0,  "move_cost": 0},
    Terrain.CONTROL_NODE: {"traversable": True,  "max_food": 0,  "regen_rate": 0, "cover": 0.15, "move_cost": 2},
}


# ── Structures ─────────────────────────────────────────────────────────────────

@dataclass
class Structure:
    type: str          # "barricade" | "collector"
    hp: int
    max_hp: int
    owner_id: str
    passable: bool

    def serialize(self) -> dict:
        return {
            "type": self.type,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "owner_id": self.owner_id,
            "passable": self.passable,
        }


STRUCTURE_DEFINITIONS = {
    "barricade": {"hp": 50, "max_hp": 50, "passable": False},
    "collector": {"hp": 20, "max_hp": 20, "passable": True},
}


# ── Wreckage ───────────────────────────────────────────────────────────────────

@dataclass
class Wreckage:
    source_bot_id: str
    source_bot_name: str
    created_cycle: int
    salvage_compute: int

    def serialize(self) -> dict:
        return {
            "type": "wreckage",
            "source_bot_id": self.source_bot_id,
            "source_bot_name": self.source_bot_name,
            "created_cycle": self.created_cycle,
            "salvage_compute": self.salvage_compute,
            "passable": True,
        }


# ── Cell ───────────────────────────────────────────────────────────────────────

@dataclass
class Cell:
    q: int
    r: int
    terrain: Terrain
    current_food: int = 0
    owner: str = "neutral"
    capture_progress: float = 0.0
    structure: Optional[Structure] = None
    wreckage: Optional[Wreckage] = None
    occupant_id: Optional[str] = None  # bot_id of bot currently on this cell

    @property
    def s(self) -> int:
        return -self.q - self.r

    @property
    def max_food(self) -> int:
        return TERRAIN_PROPERTIES[self.terrain]["max_food"]

    @property
    def regen_rate(self) -> int:
        return TERRAIN_PROPERTIES[self.terrain]["regen_rate"]

    @property
    def traversable(self) -> bool:
        return TERRAIN_PROPERTIES[self.terrain]["traversable"]

    @property
    def move_cost(self) -> int:
        return TERRAIN_PROPERTIES[self.terrain]["move_cost"]

    def is_passable(self) -> bool:
        """Can a bot move onto this cell?"""
        if not self.traversable:
            return False
        if self.structure and not self.structure.passable:
            return False
        return True

    def is_occupied(self) -> bool:
        return self.occupant_id is not None

    def serialize(self) -> dict:
        return {
            "coordinate": {"q": self.q, "r": self.r},
            "terrain": self.terrain.value,
            "max_food": self.max_food,
            "current_food": self.current_food,
            "owner": self.owner,
            "capture_progress": self.capture_progress,
            "structure": self.structure.serialize() if self.structure else None,
            "wreckage": self.wreckage.serialize() if self.wreckage else None,
            "occupant_id": self.occupant_id,
        }


# ── Board ──────────────────────────────────────────────────────────────────────

class Board:

    def __init__(self, config: dict):
        self.radius = config["radius"]
        self.boundary_type = config.get("boundary_type", "hard_wall")
        self.storm_enabled = config.get("storm_enabled", False)
        self.storm_start_cycle = config.get("storm_start_cycle")
        self.storm_shrink_interval = config.get("storm_shrink_interval")
        self.current_radius = self.radius

        # cells indexed by (q, r)
        self.cells: Dict[Tuple[int, int], Cell] = {}
        self._init_cells()

    # ── Initialisation ─────────────────────────────────────────────────────────

    def _init_cells(self):
        """Populate all valid cells with default grass terrain."""
        for q in range(-self.radius, self.radius + 1):
            for r in range(-self.radius, self.radius + 1):
                s = -q - r
                if max(abs(q), abs(r), abs(s)) <= self.radius:
                    self.cells[(q, r)] = Cell(
                        q=q, r=r,
                        terrain=Terrain.GRASS,
                        current_food=10,
                    )

    def apply_map_directive(self, directive: dict):
        """Apply Overlord map generation directives to board cells."""
        from overlord.map_generator import apply_directives
        apply_directives(self, directive)

    # ── Coordinate helpers ─────────────────────────────────────────────────────

    def is_valid(self, q: int, r: int) -> bool:
        s = -q - r
        return max(abs(q), abs(r), abs(s)) <= self.current_radius

    def get_cell(self, q: int, r: int) -> Optional[Cell]:
        return self.cells.get((q, r))

    def distance(self, q1: int, r1: int, q2: int, r2: int) -> int:
        s1 = -q1 - r1
        s2 = -q2 - r2
        return max(abs(q1 - q2), abs(r1 - r2), abs(s1 - s2))

    def neighbour(self, q: int, r: int, direction: str) -> Tuple[int, int]:
        dq, dr = DIRECTIONS[direction]
        return q + dq, r + dr

    def distance_to_edge(self, q: int, r: int) -> dict:
        """Calculate steps to board edge in each direction."""
        distances = {}
        for direction, (dq, dr) in DIRECTIONS.items():
            steps = 0
            nq, nr = q, r
            while True:
                nq += dq
                nr += dr
                if not self.is_valid(nq, nr):
                    break
                steps += 1
            distances[direction] = steps
        return distances

    # ── Food regeneration ──────────────────────────────────────────────────────

    def regenerate_food(self):
        """Phase 2: increment food on all terrain cells up to max."""
        for cell in self.cells.values():
            if cell.regen_rate > 0 and cell.current_food < cell.max_food:
                cell.current_food = min(
                    cell.current_food + cell.regen_rate,
                    cell.max_food
                )

    # ── Passive income ─────────────────────────────────────────────────────────

    def distribute_passive_income(self, bots: list):
        """Phase 2: +5 CU to collector owners and control node holders."""
        for cell in self.cells.values():
            # Collector income
            if cell.structure and cell.structure.type == "collector":
                owner_id = cell.structure.owner_id
                bot = next((b for b in bots if b.bot_id == owner_id and b.is_alive), None)
                if bot:
                    bot.compute_units = min(bot.compute_units + 5, bot.max_compute)

            # Control node income
            if cell.terrain == Terrain.CONTROL_NODE and cell.owner != "neutral":
                for bot in bots:
                    if bot.is_alive and bot.team == cell.owner:
                        bot.compute_units = min(bot.compute_units + 5, bot.max_compute)

    # ── Storm ring ─────────────────────────────────────────────────────────────

    def apply_storm(self, cycle: int):
        """Shrink board radius if storm is enabled."""
        if not self.storm_enabled:
            return
        if cycle < self.storm_start_cycle:
            return
        cycles_since_start = cycle - self.storm_start_cycle
        if cycles_since_start % self.storm_shrink_interval == 0:
            if self.current_radius > 2:
                self.current_radius -= 1
                # Convert outermost ring to asteroid
                for (q, r), cell in self.cells.items():
                    s = -q - r
                    if max(abs(q), abs(r), abs(s)) > self.current_radius:
                        cell.terrain = Terrain.ASTEROID
                        cell.current_food = 0
                        cell.structure = None

    # ── Serialisation ──────────────────────────────────────────────────────────

    def serialize(self) -> dict:
        return {
            "radius": self.radius,
            "current_radius": self.current_radius,
            "cells": {f"{q},{r}": cell.serialize() for (q, r), cell in self.cells.items()},
        }
