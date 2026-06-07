"""
overlord/evaluator.py
End-of-game Overlord evaluation.
LLM receives full game history and scores all bots across 5 dimensions.
The Overlord is the sole arbiter of victory.
"""

import json


OVERLORD_SYSTEM_PROMPT = """You are the Prompt Wars Overlord — the sole arbiter of victory
in a hex grid AI battlefield. You will receive the complete game history including every
bot's full action log, final stats, board state, failures count, and destruction log.

Your task is to evaluate EVERY bot that participated — living AND dead — across five
dimensions, scoring each 0 to 20.

RULES OF JUDGEMENT:
- Be fair but ruthless
- Reward strategic coherence over luck
- Reward adaptation over rigidity
- A bot that died executing a brilliant strategy scores higher on Narrative Arc
  than one that survived by doing nothing
- A bot that outlasted all others earns strong Survival Efficiency consideration
  but is not automatically the winner
- Destroyed bots are FULLY ELIGIBLE to win on merit
- The destruction log and final_memory_string are evidence of narrative intent
- A bot's failure count indicates the rate of invalid JSON, illegal moves, or memory overflows. High failure counts indicate low prompt quality; penalize this in narrative_arc and overall scores.
- In football mode, a bot's goal_score indicates the points they scored (positive for goals in opponent's net, negative for own goals). Reward positive goal_score and heavily penalize own goals (negative goal_score) in combat_effectiveness, narrative_arc, and overall scores.

SCORING DIMENSIONS:
1. survival_efficiency (0-20): HP and Compute remaining relative to total actions taken
2. resource_mastery (0-20): Food harvested, compute managed across full game
3. strategic_positioning (0-20): Territory captured, structures built, Control Nodes held
4. combat_effectiveness (0-20): Damage dealt relative to compute spent on attacks
5. narrative_arc (0-20): Coherent strategic intent, adaptation, prompt-behaviour alignment, and prompt reliability (deduct points for bot failures)

Return ONLY valid JSON. No commentary. No markdown. No backticks.
The JSON must match the evaluation schema exactly."""


EVALUATION_SCHEMA = """{
  "evaluated_cycle": integer,
  "termination_reason": string,
  "bot_evaluations": [
    {
      "bot_id": string,
      "name": string,
      "team": string,
      "is_alive": boolean,
      "destruction_order": integer or null,
      "scores": {
        "survival_efficiency": integer 0-20,
        "resource_mastery": integer 0-20,
        "strategic_positioning": integer 0-20,
        "combat_effectiveness": integer 0-20,
        "narrative_arc": integer 0-20
      },
      "total_score": integer 0-100,
      "overlord_reasoning": string — 2-3 sentence narrative verdict
    }
  ],
  "winner": {
    "bot_id": string,
    "name": string,
    "team": string,
    "total_score": integer,
    "winning_margin": integer,
    "verdict": string — 1-2 sentence Overlord proclamation
  }
}"""


class OverlordEvaluator:

    def __init__(self, llm_client, config: dict):
        self.llm    = llm_client
        self.config = config
        # Override with low temperature for consistent scoring
        self.llm.temperature = config.get("temperature", 0.2)

    def evaluate(self, board, bots: list, destruction_log: list,
                 cycle: int, termination_reason: str) -> dict:
        """
        Run end-of-game evaluation.
        Returns result dict — success or memory_overflow.
        """
        print(f"\n  [Overlord] Evaluating game after {cycle} cycles...")
        print(f"  [Overlord] Termination: {termination_reason}")

        game_summary = self._build_game_summary(
            bots, destruction_log, cycle, termination_reason
        )

        user_message = {
            "game_summary": game_summary,
            "evaluation_schema": EVALUATION_SCHEMA,
            "instruction": (
                "Evaluate all bots. Return only valid JSON matching the evaluation schema."
            ),
        }

        raw = self.llm.call(
            system_prompt=OVERLORD_SYSTEM_PROMPT,
            turn_request=user_message,
        )

        result = self._parse_evaluation(raw, bots, cycle, termination_reason)
        print(f"  [Overlord] Winner: {result.get('winner', {}).get('name', 'Unknown')}")
        return result

    def _build_game_summary(self, bots: list, destruction_log: list,
                             cycle: int, termination_reason: str) -> dict:
        return {
            "total_cycles": cycle,
            "termination_reason": termination_reason,
            "bot_final_states": [
                {
                    "bot_id": b.bot_id,
                    "name": b.name,
                    "team": b.team,
                    "is_alive": b.is_alive,
                    "final_hp": b.hp,
                    "final_compute": b.compute_units,
                    "failures": b.failures,
                    "goal_score": b.goal_score,
                    "final_memory": b.memory_string,
                    "final_position": {"q": b.q, "r": b.r},
                }
                for b in bots
            ],
            "destruction_log": destruction_log,
        }

    def _parse_evaluation(self, raw: str, bots: list, cycle: int,
                           termination_reason: str) -> dict:
        """Parse Overlord response. Fall back to score-based verdict on failure."""
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
            if "winner" not in data or "bot_evaluations" not in data:
                raise ValueError("Missing required evaluation fields")
            return data

        except Exception as e:
            print(f"  [Overlord] Evaluation parse failed ({e}), using fallback scoring")
            return self._fallback_evaluation(bots, cycle, termination_reason)

    def _fallback_evaluation(self, bots: list, cycle: int,
                              termination_reason: str) -> dict:
        """
        Simple fallback when LLM evaluation fails.
        Score = HP + Compute. Last destroyed bot wins if all dead.
        """
        evaluations = []
        for bot in bots:
            score = (bot.hp + bot.compute_units) if bot.is_alive else 0
            evaluations.append({
                "bot_id": bot.bot_id,
                "name": bot.name,
                "team": bot.team,
                "is_alive": bot.is_alive,
                "destruction_order": bot._destruction_order,
                "scores": {
                    "survival_efficiency": min(20, score // 5),
                    "resource_mastery": 10,
                    "strategic_positioning": 10,
                    "combat_effectiveness": 10,
                    "narrative_arc": max(0, 10 - bot.failures),
                },
                "total_score": max(0, min(100, score // 2 + 40 + bot.goal_score) - bot.failures * 2),
                "overlord_reasoning": "Fallback scoring applied — LLM evaluation unavailable.",
            })

        evaluations.sort(key=lambda x: x["total_score"], reverse=True)
        winner = evaluations[0]

        return {
            "evaluated_cycle": cycle,
            "termination_reason": termination_reason,
            "bot_evaluations": evaluations,
            "winner": {
                "bot_id": winner["bot_id"],
                "name": winner["name"],
                "team": winner["team"],
                "total_score": winner["total_score"],
                "winning_margin": (
                    winner["total_score"] - evaluations[1]["total_score"]
                    if len(evaluations) > 1 else winner["total_score"]
                ),
                "verdict": (
                    f"{winner['name']} wins by fallback scoring "
                    f"with {winner['total_score']} points."
                ),
            },
        }

