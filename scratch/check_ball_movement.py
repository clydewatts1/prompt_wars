import json
import os

project_dir = r"c:\Users\cw171001\OneDrive - Teradata\Documents\GitHub\prompt_wars"
replay_path = os.path.join(project_dir, "replay.jsonl")

if not os.path.exists(replay_path):
    print("replay.jsonl does not exist")
    exit()

print("Analyzing replay.jsonl...")

with open(replay_path, "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]

ball_positions = []
kicks = []

for line_idx, line in enumerate(lines):
    frame = json.loads(line)
    if frame.get("type") == "finale":
        print(f"Finale reached at line {line_idx}. Stats:")
        print(json.dumps(frame, indent=2))
        continue
    
    cycle_id = frame.get("cycle_id")
    board_state = frame.get("board_state", {})
    cells = board_state.get("cells", [])
    
    # Track ball positions
    ball_found = False
    for cell in cells:
        if cell.get("ball") is not None:
            ball_pos = (cell.get("q"), cell.get("r"))
            ball_vel = cell.get("ball").get("velocity_direction")
            ball_positions.append((cycle_id, ball_pos, ball_vel))
            ball_found = True
            break
            
    # Track actions
    actions_by_bot = frame.get("actions_by_bot", {})
    for bot_id, action_result in actions_by_bot.items():
        # action_result format is usually {"action": {"action": "...", ...}, "executed": True/False, ...}
        action = action_result.get("action", {})
        if action and action.get("action") == "kick":
            kicks.append((cycle_id, bot_id, action, action_result.get("executed", True)))

print(f"Total cycles: {len(lines)}")
print(f"Total kicks attempted/executed: {len(kicks)}")
for k in kicks[:10]:
    print(f"  Cycle {k[0]} - Bot {k[1]} kicked: {k[2]} (executed: {k[3]})")

print("\nBall position history (first 20 frames):")
for bp in ball_positions[:20]:
    print(f"  Cycle {bp[0]}: Position {bp[1]}, Velocity {bp[2]}")

print("\nBall position history (when moving or changing position):")
last_pos = None
for bp in ball_positions:
    if last_pos is None or bp[1] != last_pos or bp[2] is not None:
        print(f"  Cycle {bp[0]}: Position {bp[1]}, Velocity {bp[2]}")
        last_pos = bp[1]
