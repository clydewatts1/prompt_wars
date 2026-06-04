"""
game.py
Prompt Wars — CLI entry point.

Usage:
  python game.py --config config/game.json
  python game.py --config config/game.json --verbose
  python game.py --config config/game.json --replay output/replay.jsonl
"""

import argparse
import json
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.cycle import GameEngine


def main():
    parser = argparse.ArgumentParser(
        description="Prompt Wars — AI agent hex grid strategy game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python game.py --config config/game.json
  python game.py --config config/game.json --verbose
  python game.py --config config/game.json --replay output/game_001.jsonl
        """
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to game.json configuration file",
    )
    parser.add_argument(
        "--replay",
        default="replay.jsonl",
        help="Output path for replay file (default: replay.jsonl)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print turn-by-turn logs to stdout",
    )

    args = parser.parse_args()

    # Load config
    try:
        with open(args.config) as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: config file not found: {args.config}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in config: {e}")
        sys.exit(1)

    # Ensure output directory exists
    replay_dir = os.path.dirname(args.replay)
    if replay_dir:
        os.makedirs(replay_dir, exist_ok=True)

    # Run engine
    engine = GameEngine(
        config=config,
        replay_path=args.replay,
        verbose=args.verbose,
    )
    engine.run()


if __name__ == "__main__":
    main()
