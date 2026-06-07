"""
engine/cycle.py
Main game engine loop.
Phase 1: sequential bot execution
Phase 2: post-turn resolution (peek, food, income, win check)
"""

import math
import random
from engine.board import Board
from engine.bot import Bot
from engine.validator import Validator
from engine.actions import ActionResolver
from engine.peek import PeekResolver
from engine.win import WinChecker
from engine.writer import StateWriter
from llm import get_llm_client
from llm.prompts import build_handshake, build_turn_request
from overlord.map_generator import MapGenerator
from overlord.evaluator import OverlordEvaluator


class GameEngine:

    def __init__(self, config: dict, replay_path: str, verbose: bool = False, trace_path: str = None):
        self.config   = config
        self.verbose  = verbose
        self.cycle    = 0
        self.trace_path = trace_path

        # Clear trace file on start if specified
        if self.trace_path:
            try:
                with open(self.trace_path, "w", encoding="utf-8") as f:
                    f.write("# Prompt Wars LLM Call Trace\n\n")
            except Exception as e:
                print(f"Error initializing trace file: {e}")

        # Board
        self.board = Board(config["board"])

        # Bots — spawn positions distributed evenly around inner ring
        self.bots = self._init_bots(config["bots"], config["board"]["radius"])

        # Engine components
        self.validator  = Validator(config["rules"])
        self.resolver   = ActionResolver(self.board)
        self.peek_res   = PeekResolver(self.board)
        self.win_check  = WinChecker(config["rules"]["turn_limit"])
        self.writer     = StateWriter(replay_path)

        # LLM
        self.llm = get_llm_client(config["llm"], verbose=self.verbose, trace_path=self.trace_path)

        # Overlord — use same factory client with different config parameters
        overlord_llm = get_llm_client({**config["llm"], **config["overlord"]}, verbose=self.verbose, trace_path=self.trace_path)
        self.map_gen   = MapGenerator(overlord_llm, config["overlord"])
        self.evaluator = OverlordEvaluator(overlord_llm, config["overlord"])

        # State tracking
        self.destruction_log     = []
        self.pending_peeks       = []
        self.destruction_counter = [0]  # mutable int via list
        self.handshake           = build_handshake(config)

    # ── Entry point ────────────────────────────────────────────────────────────

    def run(self):
        print("\n=== PROMPT WARS ===")
        print(f"  Board radius: {self.board.radius}")
        print(f"  Bots: {len(self.bots)}")
        print(f"  Turn limit: {self.config['rules']['turn_limit']}")

        # Generate map via Overlord
        map_directive = self.map_gen.generate(self.board, len(self.bots))

        # Write handshake
        self.writer.write_handshake(
            self.config, self.board, self.bots,
            self.handshake, map_directive
        )

        print(f"\n  Starting game loop...\n")

        while True:
            self.cycle += 1
            self._log(f"=== Cycle {self.cycle} ======================")

            self._run_phase_1()
            win_result = self._run_phase_2()

            self.writer.write_cycle(
                self.cycle, self.board, self.bots,
                self.destruction_log, win_result
            )

            if not self.verbose:
                import sys
                limit = self.config["rules"]["turn_limit"]
                pct = int((self.cycle / limit) * 100) if limit > 0 else 0
                bar_len = 20
                filled_len = int(bar_len * self.cycle / limit) if limit > 0 else 0
                bar = '=' * filled_len + '-' * (bar_len - filled_len)
                sys.stdout.write(f"\r  Simulating Cycle {self.cycle}/{limit} [{bar}] {pct}%")
                sys.stdout.flush()

            if win_result["game_over"]:
                if not self.verbose:
                    print()
                print(f"\n  Game over - {win_result['termination_reason']}")
                verdict = self.evaluator.evaluate(
                    self.board, self.bots, self.destruction_log,
                    self.cycle, win_result["termination_reason"]
                )
                self.writer.write_finale(win_result, verdict)

                winner = verdict.get("winner", {})
                print(f"\n=== OVERLORD VERDICT ===")
                print(f"  Winner: {winner.get('name', 'Unknown')}")
                print(f"  Score:  {winner.get('total_score', '?')}/100")
                print(f"  Verdict: {winner.get('verdict', '')}")
                break

        if not self.verbose:
            print()
        print(f"\n=== GAME COMPLETE after {self.cycle} cycles ===\n")

    # ── Phase 1 ────────────────────────────────────────────────────────────────

    def _run_phase_1(self):
        active = [b for b in self.bots if b.is_alive]
        random.shuffle(active)
        self._log(f"  Phase 1: {len(active)} active bots")

        for bot in active:
            if not bot.is_alive:
                continue

            self._log(f"  [{bot.name}] HP:{bot.hp} CU:{bot.compute_units} pos:({bot.q},{bot.r})")

            # Compute starvation check
            if bot.compute_units <= 0:
                self.destruction_counter[0] += 1
                bot.die(
                    cycle=self.cycle,
                    destroyed_by="starvation",
                    cause="compute_exhaustion",
                    destruction_order=self.destruction_counter[0],
                )
                cell = self.board.get_cell(bot.q, bot.r)
                if cell:
                    cell.occupant_id = None
                    from engine.board import Wreckage
                    cell.wreckage = Wreckage(
                        source_bot_id=bot.bot_id,
                        source_bot_name=bot.name,
                        created_cycle=self.cycle,
                        salvage_compute=bot.salvage_compute(),
                    )
                self.destruction_log.append(bot.death_record())
                self._log(f"  [{bot.name}] STARVED")
                continue

            # Build turn request
            turn_request = build_turn_request(
                bot, self.board, self.cycle, self.config["rules"]
            )

            # Clear pending peek result after delivery
            bot.pending_peek_result = None

            # LLM call
            raw = self.llm.call(
                system_prompt=bot.system_prompt,
                turn_request=turn_request,
                handshake=self.handshake if self.cycle == 1 else None,
            )

            # Parse response
            action, error = self.validator.parse_response(raw)

            if error:
                self._log(f"  [{bot.name}] FAILED ({error['reason']})")
                # Handle memory overflow — update memory failure result
                if error["reason"] == "memory_overflow":
                    bot.record_last_turn_result("failed", error)
                else:
                    bot.record_last_turn_result("failed", error)
                continue

            # Handle memory update (separate from action execution)
            save_memory = action.get("save_memory", "")
            if save_memory:
                mem_result = bot.update_memory(save_memory, self.config["rules"]["memory_max_characters"])
                if not mem_result["success"]:
                    # Memory overflow — reject and carry forward
                    bot.record_last_turn_result("failed", {
                        **mem_result,
                        "action_attempted": action["action"],
                        "compute_deducted": 0,
                        "thought": action.get("thought", ""),
                    })
                    self._log(f"  [{bot.name}] MEMORY OVERFLOW ({mem_result['characters_submitted']} chars)")
                    continue

            # Peek — queue for Phase 2
            if action["action"] == "peek":
                self.pending_peeks.append({
                    "bot": bot,
                    "action": action,
                    "issued_cycle": self.cycle,
                })
                bot.deduct_compute(1)
                bot.record_last_turn_result("success", {
                    "action": "peek",
                    "compute_deducted": 1,
                    "thought": action.get("thought", ""),
                })
                self._log(f"  [{bot.name}] PEEK {action['direction']} (queued)")
                continue

            # Validate against board rules
            valid, val_error = self.validator.validate_action(bot, action, self.board)
            if not valid:
                self._log(f"  [{bot.name}] ILLEGAL ({val_error['detail']})")
                bot.deduct_compute(val_error.get("compute_deducted", 0))
                val_error["thought"] = action.get("thought", "")
                bot.record_last_turn_result("failed", val_error)
                continue

            # Resolve action
            cost = self.resolver.resolve(
                bot, action, self.destruction_log,
                self.bots, self.cycle, self.destruction_counter
            )
            bot.record_last_turn_result("success", {
                "action": action["action"],
                "compute_deducted": cost,
                "thought": action.get("thought", ""),
            })
            self._log(f"  [{bot.name}] {action['action'].upper()} (cost:{cost} CU remaining:{bot.compute_units})")

            # Log thought if verbose
            if self.verbose and "thought" in action:
                self._log(f"    Thought: {action['thought'][:100]}")

    # ── Phase 2 ────────────────────────────────────────────────────────────────

    def _run_phase_2(self) -> dict:
        self._log(f"  Phase 2: resolving peeks, food, income")

        # Resolve peek queue
        for item in self.pending_peeks:
            if item["bot"].is_alive:
                result = self.peek_res.resolve(
                    item["bot"], item["action"],
                    self.bots, item["issued_cycle"]
                )
                item["bot"].pending_peek_result = result
                self._log(f"  [{item['bot'].name}] PEEK resolved ({len(result['cells_scanned'])} cells)")
        self.pending_peeks.clear()

        # Food regeneration
        self.board.regenerate_food()

        # Passive income
        self.board.distribute_passive_income(self.bots)

        # Apply feed / regen
        self._apply_feed_regen()

        # Ball Physics
        self._resolve_ball_physics()

        # Storm ring (if enabled)
        self.board.apply_storm(self.cycle)

        # Win check
        return self.win_check.check(self.bots, self.cycle, self.destruction_log)

    # ── Bot initialisation ─────────────────────────────────────────────────────

    def _init_bots(self, bot_configs: list, radius: int) -> list:
        """Spawn bots evenly distributed around inner ring or at custom coordinates."""
        bots = []
        spawn_radius = max(2, radius - 2)
        n = len(bot_configs)

        for i, cfg in enumerate(bot_configs):
            if "q" in cfg and "r" in cfg:
                q, r = cfg["q"], cfg["r"]
            else:
                angle = (2 * math.pi * i) / n
                q = round(spawn_radius * math.cos(angle))
                r = round(spawn_radius * math.sin(angle))

            # Snap to valid cell
            cell = self.board.get_cell(q, r)
            if not cell or not cell.traversable:
                q, r = 0, 0  # fallback to centre

            bot = Bot(
                bot_id=cfg["bot_id"],
                name=cfg["name"],
                team=cfg["team"],
                system_prompt=cfg["system_prompt"],
                q=q,
                r=r,
            )
            cell = self.board.get_cell(q, r)
            if cell:
                cell.occupant_id = bot.bot_id

            bots.append(bot)
            print(f"  Spawned {bot.name} ({bot.team}) at q:{q} r:{r}")

        return bots

    # ── Logging ────────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    # ── Football Physics ───────────────────────────────────────────────────────

    def _resolve_ball_physics(self):
        balls_to_process = []
        for (q, r), cell in self.board.cells.items():
            if cell.ball is not None:
                balls_to_process.append((q, r, cell))

        for q, r, cell in balls_to_process:
            ball = cell.ball
            if ball["velocity_direction"] is None:
                continue

            # check age
            ball["age"] += 1
            if ball["age"] > self.board.radius * 2:
                ball["velocity_direction"] = None
                continue

            direction = ball["velocity_direction"]
            from engine.board import DIRECTIONS
            dq, dr = DIRECTIONS[direction]
            nq, nr = q + dq, r + dr

            target = self.board.get_cell(nq, nr)
            if not target:
                # hit wall, bounce
                ball["velocity_direction"] = self._reverse_direction(direction)
                continue

            if target.goal:
                # Goal scored!
                # Determine which team defends this goal
                defending_team = target.goal_owner
                if not defending_team:
                    defending_team = "red" if target.q < 0 else ("blue" if target.q > 0 else None)
                
                # Scoring team is the opponent of the defending team
                scoring_team = "blue" if defending_team == "red" else ("red" if defending_team == "blue" else None)
                
                if scoring_team and scoring_team in self.board.team_scores:
                    self.board.team_scores[scoring_team] += 1
                
                owner = next((b for b in self.bots if b.bot_id == ball["owner_id"]), None)
                if owner and owner.is_alive:
                    if owner.team == scoring_team:
                        # Regular Goal
                        owner.goal_score += target.goal_score
                        owner.add_compute(target.goal_cu)
                        owner.hp = min(owner.max_hp, owner.hp + target.goal_hp)
                        self._log(f"  GOAL by {owner.name} (+{target.goal_cu} CU, +{target.goal_hp} HP, +{target.goal_score} pts)!")
                    else:
                        # Own Goal
                        owner.goal_score -= target.goal_score
                        self._log(f"  OWN GOAL by {owner.name} (-{target.goal_score} pts)!")
                else:
                    self._log(f"  GOAL scored for team {scoring_team}!")
                
                # Reset ball
                cell.ball = None
                self._reset_ball()
                continue
            
            if not target.is_passable():
                # hit object, bounce
                if target.occupant_id:
                    ball["owner_id"] = target.occupant_id
                    ball["age"] = 0
                ball["velocity_direction"] = self._reverse_direction(direction)
                continue

            # Move ball
            target.ball = ball
            cell.ball = None

    def _reverse_direction(self, direction: str) -> str:
        rev = {
            "east": "west",
            "south_east": "north_west",
            "south_west": "north_east",
            "west": "east",
            "north_west": "south_east",
            "north_east": "south_west"
        }
        return rev.get(direction, "west")

    def _reset_ball(self):
        candidates = []
        for (q, r), cell in self.board.cells.items():
            if cell.is_passable():
                dist = (abs(q) + abs(q + r) + abs(r)) // 2
                candidates.append((dist, q, r, cell))
        
        if candidates:
            candidates.sort(key=lambda x: x[0])
            best_cell = candidates[0][3]
            best_cell.ball = {"velocity_direction": None, "owner_id": None, "age": 0}

    def _apply_feed_regen(self):
        feed_cfg = self.config.get("rules", {}).get("feed") or self.config.get("feed")
        if not feed_cfg:
            return
        
        hp_rate = feed_cfg.get("hp_regen_rate", 0)
        cu_rate = feed_cfg.get("cu_regen_rate", 0)
        hp_max  = feed_cfg.get("hp_regen_max", 100)
        cu_max  = feed_cfg.get("cu_regen_max", 100)
        
        if hp_rate <= 0 and cu_rate <= 0:
            return
            
        self._log(f"  Phase 2: applying feed regeneration (HP rate: {hp_rate}, CU rate: {cu_rate})")
        for bot in self.bots:
            if bot.is_alive:
                # Regulate HP
                if hp_rate > 0 and bot.hp < hp_max:
                    old_hp = bot.hp
                    bot.hp = min(hp_max, bot.hp + hp_rate)
                    if bot.hp != old_hp:
                        self._log(f"    [{bot.name}] Regenerated HP: {old_hp} -> {bot.hp}")
                
                # Regulate CU
                if cu_rate > 0 and bot.compute_units < cu_max:
                    old_cu = bot.compute_units
                    bot.compute_units = min(cu_max, bot.compute_units + cu_rate)
                    if bot.compute_units != old_cu:
                        self._log(f"    [{bot.name}] Regenerated CU: {old_cu} -> {bot.compute_units}")
