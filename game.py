"""
game.py
Prompt Wars - CLI entry point.

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
    # Force stdout/stderr to UTF-8 to prevent encoding crashes on Windows CP1252 terminals
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Prompt Wars - AI agent hex grid strategy game",
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
        help="Path to game.json or game.yaml configuration file",
    )
    parser.add_argument(
        "--replay",
        default="replay.jsonl",
        help="Output path for replay file (default: replay.jsonl)",
    )
    parser.add_argument(
        "--trace",
        default="trace.yaml",
        help="Output path for prompt trace file (default: trace.yaml)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print turn-by-turn logs to stdout",
    )

    args = parser.parse_args()

    # Load config
    try:
        _, ext = os.path.splitext(args.config.lower())
        with open(args.config, "r", encoding="utf-8") as f:
            if ext in ('.yaml', '.yml'):
                import yaml
                config = yaml.safe_load(f)
            else:
                config = json.load(f)
    except FileNotFoundError:
        print(f"Error: config file not found: {args.config}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: failed to parse config file {args.config}: {e}")
        sys.exit(1)

    # Ensure output directories exist
    replay_dir = os.path.dirname(args.replay)
    if replay_dir:
        os.makedirs(replay_dir, exist_ok=True)
    if args.trace:
        trace_dir = os.path.dirname(args.trace)
        if trace_dir:
            os.makedirs(trace_dir, exist_ok=True)

    # Run engine
    engine = GameEngine(
        config=config,
        replay_path=args.replay,
        verbose=args.verbose,
        trace_path=args.trace,
    )
    engine.run()


if __name__ == "__main__":
    main()
