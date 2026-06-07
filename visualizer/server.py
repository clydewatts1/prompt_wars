from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import os
import json

app = Flask(__name__, static_folder='frontend/dist')
CORS(app)

# The root directory of the prompt_wars repo
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@app.route('/api/config')
def get_config():
    # 1. Try to extract config from active replay handshake first (keeps in sync with the replay being visualized)
    replay_candidates = ['replay.json', 'replay_game.json', 'replay.jsonl']
    replay_existing = [os.path.join(PROJECT_ROOT, c) for c in replay_candidates if os.path.exists(os.path.join(PROJECT_ROOT, c))]
    if replay_existing:
        replay_path = max(replay_existing, key=os.path.getmtime)
        try:
            _, ext = os.path.splitext(replay_path.lower())
            if ext == '.json':
                with open(replay_path, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                    for record in records:
                        if record.get('type') == 'handshake':
                            cfg = record.get('config')
                            if cfg:
                                return jsonify(cfg)
            else:
                with open(replay_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            if data.get('type') == 'handshake':
                                cfg = data.get('config')
                                if cfg:
                                    return jsonify(cfg)
        except Exception:
            pass

    # 2. Fallback to config directory if no replay files exist
    config_dir = os.path.join(PROJECT_ROOT, 'config')
    candidates = ['game.json', 'game.yaml', 'game.yml']
    config_path = None
    for candidate in candidates:
        path = os.path.join(config_dir, candidate)
        if os.path.exists(path):
            config_path = path
            break

    if config_path:
        try:
            _, ext = os.path.splitext(config_path.lower())
            with open(config_path, 'r', encoding='utf-8') as f:
                if ext in ('.yaml', '.yml'):
                    import yaml
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            # Load and merge external bot configs if specified
            if "bots" in data and isinstance(data["bots"], list):
                config_dir = os.path.dirname(os.path.abspath(config_path))
                for i, bot_entry in enumerate(data["bots"]):
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
                        if target_path:
                            with open(target_path, "r", encoding="utf-8") as bf:
                                _, b_ext = os.path.splitext(target_path.lower())
                                if b_ext in ('.yaml', '.yml'):
                                    import yaml
                                    bot_data = yaml.safe_load(bf)
                                else:
                                    bot_data = json.load(bf)
                            
                            merged_bot = bot_data.copy()
                            merged_bot.update(bot_entry)
                            data["bots"][i] = merged_bot
            return jsonify(data)
        except Exception:
            pass

    return jsonify({"error": "No configuration file or handshake record found"}), 404

@app.route('/api/replay')
def get_replay():
    candidates = ['replay.json', 'replay_game.json', 'replay.jsonl']
    existing_paths = [os.path.join(PROJECT_ROOT, c) for c in candidates if os.path.exists(os.path.join(PROJECT_ROOT, c))]
    
    if not existing_paths:
        return jsonify([])
        
    replay_path = max(existing_paths, key=os.path.getmtime)
    cycles = []
    try:
        _, ext = os.path.splitext(replay_path.lower())
        if ext == '.json':
            with open(replay_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
                for record in records:
                    if record.get('type') == 'cycle':
                        cycles.append(record)
        else:
            with open(replay_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        if data.get('type') == 'cycle':
                            cycles.append(data)
        return jsonify(cycles)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/finale')
def get_finale():
    candidates = ['replay.json', 'replay_game.json', 'replay.jsonl']
    existing_paths = [os.path.join(PROJECT_ROOT, c) for c in candidates if os.path.exists(os.path.join(PROJECT_ROOT, c))]
    
    if not existing_paths:
        return jsonify(None)
        
    # Sort by mtime, newest first
    existing_paths.sort(key=os.path.getmtime, reverse=True)
    
    # Only return the finale for the latest/active replay file to prevent loading stale finale data
    latest_replay_path = existing_paths[0]
    try:
        _, ext = os.path.splitext(latest_replay_path.lower())
        if ext == '.json':
            with open(latest_replay_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
                for record in records:
                    if record.get('type') == 'finale':
                        return jsonify(record)
        else:
            with open(latest_replay_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        if data.get('type') == 'finale':
                            return jsonify(data)
    except Exception:
        pass
            
    return jsonify(None)

# Serve React App
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    # Auto-open browser on startup (only once, avoiding reloader duplicate)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        import webbrowser
        import threading
        import time
        def open_browser():
            time.sleep(1.5)
            webbrowser.open("http://localhost:5000")
        threading.Thread(target=open_browser, daemon=True).start()

    app.run(port=5000, debug=True)
