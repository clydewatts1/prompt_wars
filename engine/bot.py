"""
engine/bot.py
Bot state — HP, compute, memory, position, telemetry
"""

import math
from dataclasses import dataclass, field
from typing import Optional


MAX_HP      = 100
MAX_COMPUTE = 100


@dataclass
class Bot:
    bot_id: str
    name: str
    team: str
    system_prompt: str

    # Vital stats
    hp: int = MAX_HP
    compute_units: int = MAX_COMPUTE
    max_hp: int = MAX_HP
    max_compute: int = MAX_COMPUTE

    # Position (axial coords)
    q: int = 0
    r: int = 0

    # Memory
    memory_string: str = ""

    # State
    is_alive: bool = True
    status_effects: list = field(default_factory=list)
    failures: int = 0
    goal_score: int = 0

    # Turn tracking
    last_turn_result: dict = field(default_factory=lambda: {
        "status": "none",
        "reason": None,
        "detail": None,
        "action_attempted": None,
        "compute_deducted": 0,
        "characters_submitted": None,
        "characters_allowed": None,
        "attempted_save_memory": None,
        "thought": None,
    })
    pending_peek_result: Optional[dict] = None

    # Death tracking
    _destruction_order: Optional[int] = None
    _destroyed_cycle: Optional[int] = None
    _destroyed_by: Optional[str] = None
    _cause: Optional[str] = None
    _final_compute: Optional[int] = None
    _final_memory: Optional[str] = None
    _final_position: Optional[dict] = None

    # ── Compute management ─────────────────────────────────────────────────────

    def deduct_compute(self, amount: int):
        self.compute_units = max(0, self.compute_units - amount)

    def add_compute(self, amount: int):
        self.compute_units = min(self.max_compute, self.compute_units + amount)

    def starvation_warning(self, threshold: int) -> bool:
        return self.compute_units <= threshold

    # ── HP management ─────────────────────────────────────────────────────────

    def take_damage(self, amount: int):
        self.hp = max(0, self.hp - amount)

    # ── Memory management ──────────────────────────────────────────────────────

    def update_memory(self, new_memory: str, max_chars: int) -> dict:
        """
        Attempt to update memory string.
        Returns result dict — success or memory_overflow.
        """
        if len(new_memory) > max_chars:
            return {
                "success": False,
                "reason": "memory_overflow",
                "characters_submitted": len(new_memory),
                "characters_allowed": max_chars,
                "attempted_save_memory": new_memory,
            }
        self.memory_string = new_memory
        return {"success": True}

    # ── Turn result recording ──────────────────────────────────────────────────

    def record_last_turn_result(self, status: str, data: dict):
        """Record the outcome of the last turn for delivery next cycle."""
        if status == "success":
            self.last_turn_result = {
                "status": "success",
                "reason": None,
                "detail": None,
                "action_attempted": data.get("action"),
                "compute_deducted": data.get("compute_deducted", 0),
                "characters_submitted": None,
                "characters_allowed": None,
                "attempted_save_memory": None,
                "thought": data.get("thought"),
            }
        else:
            self.failures += 1
            self.last_turn_result = {
                "status": "failed",
                "reason": data.get("reason"),
                "detail": data.get("detail"),
                "action_attempted": data.get("action_attempted"),
                "compute_deducted": data.get("compute_deducted", 0),
                "characters_submitted": data.get("characters_submitted"),
                "characters_allowed": data.get("characters_allowed"),
                "attempted_save_memory": data.get("attempted_save_memory"),
                "thought": data.get("thought"),
            }

    # ── Death ──────────────────────────────────────────────────────────────────

    def die(self, cycle: int, destroyed_by: str, cause: str, destruction_order: int):
        """Mark bot as dead and capture final state snapshot."""
        self._final_compute  = self.compute_units
        self._final_memory   = self.memory_string
        self._final_position = {"q": self.q, "r": self.r}
        self._destroyed_cycle = cycle
        self._destroyed_by    = destroyed_by
        self._cause           = cause
        self._destruction_order = destruction_order
        self.hp = 0
        self.is_alive = False

    def salvage_compute(self) -> int:
        """
        Compute value of wreckage left on death.
        Formula: 10 + floor(final_compute * 0.75)
        """
        fc = self._final_compute if self._final_compute is not None else 0
        return 10 + math.floor(fc * 0.75)

    def death_record(self) -> dict:
        """Full destruction log entry."""
        fc = self._final_compute if self._final_compute is not None else 0
        return {
            "bot_id": self.bot_id,
            "name": self.name,
            "team": self.team,
            "destroyed_cycle": self._destroyed_cycle,
            "destruction_order": self._destruction_order,
            "destroyed_by": self._destroyed_by,
            "cause": self._cause,
            "final_hp": 0,
            "final_compute": fc,
            "salvage_compute": self.salvage_compute(),
            "salvage_formula": f"10 + floor({fc} x 0.75)",
            "final_position": self._final_position,
            "final_memory_string": self._final_memory,
        }

    # ── Serialisation ──────────────────────────────────────────────────────────

    def serialize(self) -> dict:
        return {
            "bot_id": self.bot_id,
            "name": self.name,
            "team": self.team,
            "position": {"q": self.q, "r": self.r},
            "hp": self.hp,
            "max_hp": self.max_hp,
            "compute_units": self.compute_units,
            "max_compute": self.max_compute,
            "memory_string": self.memory_string,
            "is_alive": self.is_alive,
            "last_turn_result": self.last_turn_result,
            "status_effects": self.status_effects,
            "failures": self.failures,
            "goal_score": self.goal_score,
        }
