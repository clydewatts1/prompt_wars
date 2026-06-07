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

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Manual fallback parser for .env files if package not yet installed
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

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
        
        # Load and merge external bot configs if specified
        if "bots" in config and isinstance(config["bots"], list):
            config_dir = os.path.dirname(os.path.abspath(args.config))
            for i, bot_entry in enumerate(config["bots"]):
                if isinstance(bot_entry, dict) and "file" in bot_entry:
                    bot_file = bot_entry["file"]
                    path1 = os.path.join(config_dir, bot_file)
                    path2 = os.path.join(os.path.dirname(config_dir), bot_file)
                    path3 = os.path.abspath(bot_file)
                    
                    target_path = None
                    for p in [path1, path2, path3]:
                        if os.path.exists(p):
                            target_path = p
                            break
                    if not target_path:
                        print(f"Error: bot config file not found: {bot_file}")
                        sys.exit(1)
                        
                    with open(target_path, "r", encoding="utf-8") as bf:
                        _, b_ext = os.path.splitext(target_path.lower())
                        if b_ext in ('.yaml', '.yml'):
                            import yaml
                            bot_data = yaml.safe_load(bf)
                        else:
                            bot_data = json.load(bf)
                    
                    # Merge: bot_entry overrides bot_data
                    merged_bot = bot_data.copy()
                    merged_bot.update(bot_entry)
                    config["bots"][i] = merged_bot
    except FileNotFoundError:
        print(f"Error: config file not found: {args.config}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: failed to parse config file {args.config}: {e}")
        sys.exit(1)

    # Validate Gemini provider API key
    llm_provider = config.get("llm", {}).get("provider", "ollama").lower()
    if llm_provider == "gemini":
        gemini_key = config.get("llm", {}).get("api_key") or os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            print("\n" + "="*80)
            print("ERROR: GEMINI_API_KEY is not defined!")
            print("To use the 'gemini' provider, you must either:")
            print("  1. Create a '.env' file in the root folder with: GEMINI_API_KEY=your_key")
            print("  2. Set the GEMINI_API_KEY environment variable in your terminal")
            print("  3. Define 'api_key' inside config.yaml under the 'llm' section")
            print("="*80 + "\n")
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
