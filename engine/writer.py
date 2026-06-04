"""
engine/writer.py
State writer — appends one JSON record per line to replay.jsonl after every Phase 2.
JSONL format means frontend can start rendering before game finishes.
Each cycle is a self-contained record.
"""

import json
from datetime import datetime
from engine.board import Board
from engine.bot import Bot


class StateWriter:

    def __init__(self, path: str):
        self.path = path
        self.records = []
        # Clear file on start
        with open(path, "w", encoding="utf-8") as f:
            pass

    def _append(self, record: dict):
        self.records.append(record)
        import os
        _, ext = os.path.splitext(self.path.lower())
        if ext == '.json':
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.records, f, indent=2)
        else:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

    def write_handshake(self, config: dict, board: Board, bots: list,
                         handshake: dict, map_directive: dict):
        """Written once at game start."""
        self._append({
            "type": "handshake",
            "timestamp": datetime.utcnow().isoformat(),
            "protocol_version": "1.7",
            "config": config,
            "handshake": handshake,
            "map_directive": map_directive,
            "board_initial": board.serialize(),
            "spawn_positions": [
                {"bot_id": b.bot_id, "name": b.name, "q": b.q, "r": b.r}
                for b in bots
            ],
        })

    def write_cycle(self, cycle_id: int, board: Board, bots: list,
                     destruction_log: list, win_check: dict):
        """Written after every Phase 2."""
        self._append({
            "type": "cycle",
            "cycle_id": cycle_id,
            "board_state": board.serialize(),
            "bot_states": [b.serialize() for b in bots],
            "destruction_log": destruction_log,
            "overlord_evaluation": {
                "game_over": win_check["game_over"],
                "termination_reason": win_check.get("termination_reason"),
                "winner": None,
            },
        })

    def write_finale(self, win_check: dict, verdict: dict):
        """Written once at game end."""
        self._append({
            "type": "finale",
            "timestamp": datetime.utcnow().isoformat(),
            "termination_reason": win_check["termination_reason"],
            "cycle_terminated": win_check["cycle"],
            "survivors": win_check.get("survivors", []),
            "destruction_log": win_check.get("destruction_log", []),
            "overlord_verdict": verdict,
        })
        print(f"\n  [Writer] Replay saved to {self.path}")
