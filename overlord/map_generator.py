"""
overlord/map_generator.py
Hybrid map generation:
  1. Overlord LLM generates a strategic map_directive (concept only, no coordinates)
  2. Procedural generator interprets directives into valid (q,r) cell data

The LLM never outputs coordinates — it thinks in strategy.
The algorithm thinks in coordinates.
"""

import json
import math
import random
from engine.board import Board, Cell, Terrain


# ── Overlord map generation prompt ────────────────────────────────────────────

MAP_SYSTEM_PROMPT = """You are the Prompt Wars Overlord. You are designing a battlefield
for AI agents on a hexagonal arena. Your job is to create a strategically interesting map.

Choose ONE strategic_intent from this exact list:
["funnel", "open", "fortress", "contested", "asymmetric", "labyrinth"]

Then issue placement directives using natural location terms:
centre, north, south, east, west, north_east, north_west, south_east, south_west

Feature types available: forest_cluster, asteroid_ridge, control_node, open_ground, grass_field

Be creative with map_name and description — these appear in the game UI.
Return ONLY valid JSON. No commentary. No markdown. No backticks."""

MAP_USER_TEMPLATE = """Design a battlefield for {num_bots} AI agents.
Board radius: {radius} ({total_cells} total cells).

Return JSON matching this exact schema:
{{
  "map_name": "string",
  "description": "string — one sentence strategic summary",
  "strategic_intent": "funnel|open|fortress|contested|asymmetric|labyrinth",
  "directives": [
    {{
      "feature": "forest_cluster|asteroid_ridge|control_node|open_ground|grass_field",
      "location": "centre|north|south|east|west|north_east|north_west|south_east|south_west",
      "density": "low|medium|high",
      "radius": 1-4,
      "count": 1-5,
      "orientation": "north_south|east_west"
    }}
  ],
  "food_distribution": "clustered|spread|sparse",
  "control_node_count": 1-3
}}"""


class MapGenerator:

    def __init__(self, llm_client, config: dict):
        self.llm = llm_client
        self.config = config

    def generate(self, board: Board, num_bots: int) -> dict:
        """
        Generate map directive via Overlord LLM then apply to board.
        Returns the directive dict for inclusion in replay.jsonl handshake.
        """
        # If board already contains goals, this is a football match.
        # Bypass Overlord LLM map generation to guarantee a clean, perfectly symmetric pitch without obstacles.
        if any(cell.goal for cell in board.cells.values()):
            directive = {
                "map_name": "Football Stadium",
                "description": "A perfectly symmetric grassy pitch with forest boundaries.",
                "strategic_intent": "symmetric_football",
                "directives": [],
                "food_distribution": "spread",
                "control_node_count": 0,
            }
            print(f"  [Overlord] Football mode detected (goals exist on board). Skipping LLM map generation and applying symmetric football pitch.")
            apply_directives(board, directive)
            return directive

        if "map_directive" in self.config:
            directive = self.config["map_directive"]
            print(f"  [Overlord] Using fixed map directive: '{directive.get('map_name', 'Custom')}'")
            apply_directives(board, directive)
            return directive

        total_cells = 3 * board.radius**2 + 3 * board.radius + 1
        
        user_template = self.config.get("map_user_prompt", MAP_USER_TEMPLATE)
        system_prompt = self.config.get("map_system_prompt", MAP_SYSTEM_PROMPT)

        user_msg = user_template.format(
            num_bots=num_bots,
            radius=board.radius,
            total_cells=total_cells,
        )

        print(f"  [Overlord] Generating map for radius={board.radius}, bots={num_bots}...")
        raw = self.llm.call(
            system_prompt=system_prompt,
            turn_request={"message": user_msg},
        )

        directive = self._parse_directive(raw, board.radius)
        print(f"  [Overlord] Map: '{directive['map_name']}' ({directive.get('strategic_intent', 'unknown')})")

        apply_directives(board, directive)
        return directive

    def _parse_directive(self, raw: str, radius: int) -> dict:
        """Parse LLM response. Fall back to default open map on failure."""
        try:
            cleaned = raw.strip() if raw else ""
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned) if cleaned else {}
            # Validate required fields
            if "strategic_intent" not in data or "map_name" not in data:
                raise ValueError("Missing required fields")
            return data
        except Exception as e:
            print(f"  [Overlord] Map directive parse failed ({e}), using default open map")
            return _default_directive(radius)


# ── Directive application ──────────────────────────────────────────────────────

def apply_directives(board: Board, directive: dict):
    """Apply a map directive to board cells. Called after board is initialised."""
    intent = directive.get("strategic_intent", "open")
    directives = directive.get("directives", [])

    generator = INTENT_GENERATORS.get(intent, _generate_open)
    generator(board, directive)


# ── Location helpers ───────────────────────────────────────────────────────────

LOCATION_VECTORS = {
    "centre":     (0.0,  0.0),
    "north":      (0.0, -1.0),
    "south":      (0.0,  1.0),
    "east":       (1.0,  0.0),
    "west":       (-1.0, 0.0),
    "north_east": (0.7, -0.7),
    "north_west": (-0.7,-0.7),
    "south_east": (0.7,  0.7),
    "south_west": (-0.7, 0.7),
}


def _location_to_axial(location: str, radius: int, scale: float = 0.6):
    """Convert a named location to approximate axial (q, r) coordinates."""
    vx, vy = LOCATION_VECTORS.get(location, (0.0, 0.0))
    q = round(vx * radius * scale)
    r = round(vy * radius * scale)
    return q, r


def _cells_in_radius(board: Board, cq: int, cr: int, r: int) -> list:
    """Return all valid board cells within axial distance r of (cq, cr)."""
    result = []
    for dq in range(-r, r + 1):
        for dr in range(-r, r + 1):
            if abs(dq) + abs(dr) + abs(-dq - dr) <= 2 * r:
                q, r2 = cq + dq, cr + dr
                cell = board.get_cell(q, r2)
                if cell:
                    result.append(cell)
    return result


# ── Strategic intent generators ────────────────────────────────────────────────

def _generate_open(board: Board, directive: dict):
    """Mostly open terrain. Sparse asteroids. Food spread evenly."""
    radius = board.radius
    for cell in board.cells.values():
        dist = max(abs(cell.q), abs(cell.r), abs(-cell.q - cell.r))
        if dist == radius:
            cell.terrain = Terrain.FOREST
            cell.current_food = 30
        elif random.random() < 0.05:
            cell.terrain = Terrain.ASTEROID
            cell.current_food = 0
        else:
            cell.terrain = Terrain.GRASS
            cell.current_food = random.randint(5, 15)

    _place_control_nodes(board, directive.get("control_node_count", 1))


def _generate_funnel(board: Board, directive: dict):
    """Asteroid ridges create narrow corridors forcing contact."""
    radius = board.radius

    # Place asteroid ridges
    for _ in range(3):
        ridge_q = random.randint(-radius // 2, radius // 2)
        for r_offset in range(-radius + 1, radius):
            cell = board.get_cell(ridge_q, r_offset)
            if cell and random.random() < 0.7:
                cell.terrain = Terrain.ASTEROID
                cell.current_food = 0

    # Forest clusters on flanks
    for location in ["north_west", "south_east"]:
        cq, cr = _location_to_axial(location, radius)
        for cell in _cells_in_radius(board, cq, cr, 3):
            if cell.terrain != Terrain.ASTEROID:
                cell.terrain = Terrain.FOREST
                cell.current_food = random.randint(20, 40)

    _fill_remaining_grass(board)
    _place_control_nodes(board, directive.get("control_node_count", 1))


def _generate_fortress(board: Board, directive: dict):
    """Dense cover clusters. Many hiding spots."""
    radius = board.radius
    locations = ["north", "south", "east", "west", "north_east", "south_west"]
    for loc in locations[:4]:
        cq, cr = _location_to_axial(loc, radius, scale=0.5)
        cluster_r = random.randint(2, 3)
        for cell in _cells_in_radius(board, cq, cr, cluster_r):
            cell.terrain = Terrain.FOREST
            cell.current_food = random.randint(25, 50)

    _fill_remaining_grass(board)
    _place_control_nodes(board, directive.get("control_node_count", 1))


def _generate_contested(board: Board, directive: dict):
    """Multiple control nodes spread across map. Territory dominates."""
    _generate_open(board, directive)
    _place_control_nodes(board, max(directive.get("control_node_count", 3), 3))


def _generate_asymmetric(board: Board, directive: dict):
    """One side resource rich, one side defensively covered."""
    radius = board.radius

    # East side — rich food
    for cell in board.cells.values():
        if cell.q > 0:
            cell.terrain = Terrain.GRASS
            cell.current_food = random.randint(15, 20)
        elif cell.q < -radius // 3:
            # West side — forest cover
            cell.terrain = Terrain.FOREST
            cell.current_food = random.randint(30, 50)
        else:
            cell.terrain = Terrain.GROUND
            cell.current_food = 0

    _place_control_nodes(board, directive.get("control_node_count", 1))


def _generate_labyrinth(board: Board, directive: dict):
    """Asteroid walls create maze-like navigation."""
    radius = board.radius

    # Scattered asteroid walls
    for _ in range(radius * 3):
        q = random.randint(-radius + 1, radius - 1)
        r = random.randint(-radius + 1, radius - 1)
        s = -q - r
        if max(abs(q), abs(r), abs(s)) < radius:
            cell = board.get_cell(q, r)
            if cell:
                length = random.randint(2, 4)
                dq, dr = random.choice([(1, 0), (0, 1), (1, -1)])
                for i in range(length):
                    nc = board.get_cell(q + dq * i, r + dr * i)
                    if nc:
                        nc.terrain = Terrain.ASTEROID
                        nc.current_food = 0

    _fill_remaining_grass(board)
    _place_control_nodes(board, directive.get("control_node_count", 2))


def _generate_symmetric_football(board: Board, directive: dict):
    """Perfectly symmetric field: grass everywhere, forest on top/bottom edges, NO rocks."""
    radius = board.radius
    threshold = max(2, radius - 3)
    for cell in board.cells.values():
        if abs(cell.r) >= threshold:
            cell.terrain = Terrain.FOREST
            cell.current_food = random.randint(10, 20)
        else:
            cell.terrain = Terrain.GRASS
            cell.current_food = random.randint(5, 15)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _fill_remaining_grass(board: Board):
    """Set any unassigned ground cells to grass with modest food."""
    for cell in board.cells.values():
        if cell.terrain == Terrain.GROUND:
            cell.terrain = Terrain.GRASS
            cell.current_food = random.randint(5, 15)


def _place_control_nodes(board: Board, count: int):
    """Place control nodes at evenly distributed positions."""
    radius = board.radius
    placed = 0
    for i in range(count):
        angle = (2 * math.pi * i) / count
        q = round(radius * 0.4 * math.cos(angle))
        r = round(radius * 0.4 * math.sin(angle))
        cell = board.get_cell(q, r)
        if cell and cell.terrain != Terrain.ASTEROID:
            cell.terrain = Terrain.CONTROL_NODE
            cell.current_food = 0
            placed += 1


def _default_directive(radius: int) -> dict:
    """Fallback map directive when LLM fails."""
    return {
        "map_name": "The Open Plain",
        "description": "A wide open battlefield with scattered forest cover.",
        "strategic_intent": "open",
        "directives": [],
        "food_distribution": "spread",
        "control_node_count": 1,
        "generated_by": "fallback",
    }


# ── Intent router ──────────────────────────────────────────────────────────────

INTENT_GENERATORS = {
    "funnel":     _generate_funnel,
    "open":       _generate_open,
    "fortress":   _generate_fortress,
    "contested":  _generate_contested,
    "asymmetric": _generate_asymmetric,
    "labyrinth":  _generate_labyrinth,
    "symmetric_football": _generate_symmetric_football,
}
