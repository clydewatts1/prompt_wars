# ⚔️ Prompt Wars

> **Status:** Early development version (Pre-Alpha)

**Prompt Wars** is an asynchronous, spatial multi-agent AI strategy game played on a hexagonal grid, heavily inspired by classic programming games like *Core War*, *Screeps*, and *Halite*. 

Instead of writing traditional deterministic code (loops, conditional checks), players write **LLM System Prompts**. These prompts define the behavior, strategy, and personality of their agents (Bots) as they compete, survive, forage, build, and adapt on the battlefield.

For the exhaustive specification, check out the [Prompt Wars Game Design & Architecture Document](file:///c:/Users/cw171001/OneDrive%20-%20Teradata/Documents/GitHub/prompt_wars/Prompt%20Wars_%20Game%20Design%20&%20Architecture.md).

---

## 🏗️ System Architecture

Prompt Wars runs on a decoupled, backend-frontend model:
1. **Game Backend (Python Engine):** Renders no graphics. It manages the core simulation, handles game mechanics (HP, Compute, grid movement, weapon resolution), compiles radar/telemetry, and orchestrates sequential API calls to a local LLM (Ollama).
2. **Replay Log (`replay.jsonl`):** Every turn, action, telemetry frame, and raw ReAct "thought" is logged to a local JSON Lines file.
3. **Game Frontend (Visualizer):** Renders the visual hex board, unit tokens, and displays step-by-step agent reasoning logs using the replay file.

---

## 🎮 Core Gameplay Mechanics

### 🧭 Hexagonal Coordinates
The board is a **pointy-topped hexagonal grid** using an **Axial Coordinate System** $(q, r)$, which is a 2D projection of 3D Cube Coordinates $(q, r, s)$, satisfying the invariant:
$$q + r + s = 0 \implies s = -q - r$$

All coordinate calculations, distance calculations, and movements use the six compass direction vectors:
* **East (E):** `(1, 0)`
* **South-East (SE):** `(0, 1)`
* **South-West (SW):** `(-1, 1)`
* **West (W):** `(-1, 0)`
* **North-West (NW):** `(0, -1)`
* **North-East (NE):** `(1, -1)`

---

### 🗺️ Terrain Ecosystem

Each hex cell has unique attributes influencing movement speed, defense cover, and resource yields:

| Terrain Type | Traversable? | Food Pool | Cover Bonus | Capture Cost | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ground (Dirt)** | Yes | 0 | 0% | 1 Turn | Basic paths. Cheap and fast to cross (2 Compute). |
| **Grass** | Yes | Low-Med (20) | 10% | 2 Turns | Regenerating meadows. Slows movement (2 Compute). |
| **Tree (Forest)** | Yes | High (50) | 30% | 3 Turns | Resource-rich forests. High movement cost (4 Compute). |
| **Asteroid (Rock)**| No | 0 | 100% | N/A | Impassable obstacle. Completely blocks lasers and peek sweeps. |
| **Control Node** | Yes | 0 | 15% | 2 Turns | Strategic hex. Controlling it provides passive team Compute. |

---

### 🤖 Bot States & ReAct Loop
On every turn, each bot receives a **Telemetry Frame** (radar data, coordinates, current HP, and Compute) and its own compressed **Memory String** from the previous turn. It must respond with a ReAct payload:
1. **`thought`**: A plain-text reasoning sequence explaining its strategic choices.
2. **`action`**: A single command from the actions vocabulary.
3. **`save_memory`**: A compressed string (up to 400 characters) containing key details it needs to remember for the next turn.

### ⚽ Football Mode
When `football_mode: true` is enabled in the configuration file, Prompt Wars transforms into a soccer-like team match with the following unique elements:
* **The Ball:** Spawns at the center (default `[0, 0]`) and moves when kicked.
* **Team Goals:** Strategic net hexes positioned on opposite sides of the board (e.g., Red goal at `[-8, 0]`, Blue goal at `[8, 0]`). Scoring in the opponent's goal increases the team's score.
* **Rocks:** Hard obstacle elements blocking movement. Unlike Asteroids, rocks are movable and can be pushed by bots to dynamic tactical locations.

---

## ⚔️ Commands Vocabulary

Bots can perform one of the following commands each turn:

| Action Command | Parameter Needed | Compute Cost | Game Effect |
| :--- | :--- | :--- | :--- |
| `"next"` | None | 0 | Skip turn, conserving compute pool. |
| `"move"` | `"direction"` | 2 (Ground) / 4 (Forest) | Step 1 hex in the target direction. |
| `"eat"` | None | 1 | Harvest food from current hex, or salvage 30 Compute from wreckage. |
| `"capture"` | None | 3 | Claim or progress control over the current hex. |
| `"attack"` | `"direction"` | 5 | Fire a linear laser beam up to Range 2, dealing 20 damage. |
| `"peek"` | `"direction"` | 1 | Run an active directional radar sweep up to Range 3. |
| `"build"` | `"direction"`, `"target_structure"` | 8 | Build a structure (`barricade` or `collector`) on an adjacent hex. |
| `"push"` | `"direction"`, `"energy"` | `energy` (variable) | Slide an adjacent rock in the target direction (cost is 1 Compute per hex traveled). |
| `"kick"` | `"direction"` | 3 | Kick the adjacent ball in the target direction. |

### 🚧 Construction & Structures
Bots can construct adjacent structures to manipulate the battlefield:
* **Barricade (50 HP):** Block passage and absorb laser hits. Used for defensive fortifications and blocking line-of-sight.
* **Collector (20 HP):** Must be placed on Grass or Tree tiles. Generates +5 passive Compute Units for the owner's team every turn.

When destroyed, structures leave behind **Wreckage** containing scrap that bots can `eat` to recover Compute.

---

## 🚀 Running the Game

### 1. Install Dependencies
Ensure you have the required packages installed in your virtual environment:
```bash
pip install -r requirements.txt
```

### 2. Run a Game Simulation
Run the simulation backend, passing a game configuration file (supports both `.json` and `.yaml`/`.yml` formats):

* **Standard Battlemode:**
  ```bash
  python game.py --config config/game.yaml
  ```

* **Football Mode:**
  To simulate a soccer-like match with goals, a ball, and pushable rocks, run:
  ```bash
  python game.py --config config/game_football.yaml --replay replay.jsonl
  ```
  *(Note: Setting `--replay replay.jsonl` ensures the web visualizer automatically picks up and renders the football match).*

  If you want to view the pre-simulated demo football match directly in the visualizer, copy the backup replay file to the default location:
  ```bash
  cp replay_football.jsonl replay.jsonl
  ```

### 3. Optional Command-Line Flags
* **Enable Verbose Output:** Prints turn-by-turn logs to stdout.
  ```bash
  python game.py --config config/game.yaml --verbose
  ```
* **Custom Replay File:** Specify a custom file path for the replay logs (defaults to `replay.jsonl`).
  ```bash
  python game.py --config config/game.yaml --replay output/my_match.jsonl
  ```

---

## 🖥️ Running the Web Visualizer

The game includes a sleek, interactive React-based visualizer map to play back and inspect simulated matches:

### 1. Install Visualizer Dependencies
Install the required Python packages for the backend server:
```bash
pip install -r visualizer/requirements.txt
```

### 2. Start the Backend Server
Run the Flask server from the root of the repository:
```bash
python visualizer/server.py
```
This runs a local server on port `5000` serving the visualizer.

### 3. Open the Visualizer
Open [http://localhost:5000](http://localhost:5000) in your web browser.

### 4. Key Visualizer Features:
* **Battlefield Playback Controls:** Play, pause, timeline scrubbing, speed control, and a "Live Sync" mode that automatically loads new turns as they are simulated.
* **Overlord Winner Banner:** Confetti-accented glassmorphic standings card with team-specific glowing colors, dynamically displaying the winning bot, score, and the Overlord's strategic match verdict.
* **Adaptive Dark Mode:** Modern web layout that automatically adapts to your system preferences (light/dark theme) using tailored HSL color tokens.
* **ReAct Log HUD:** Click on any bot on the map to see its real-time HP, Compute, Memory string, and historical decision-making traces in the sidebar.
* **System Prompt Hover Tooltips:** Hover over the `ℹ️` icon next to any bot's name in the sidebar to review its system prompt configuration.
* **Arbitrary Replay Loading:** The visualizer handles arbitrary replay files like `replay.json`, `replay_game.json`, and `replay.jsonl`. If configuration files in `config/` are deleted or mismatch, the visualizer automatically recovers and syncs the exact bot prompts and rules embedded inside the replay file's initial `handshake` record.

---

## 🛠️ Configuration

Matches can be configured using JSON or YAML files:
* **YAML format (Ollama):** [config/game.yaml](file:///c:/Users/cw171001/OneDrive%20-%20Teradata/Documents/GitHub/prompt_wars/config/game.yaml) (Recommended - easier to format and write system prompts)
* **YAML format (Google Gemini):** [config/game_gemini.yaml](file:///c:/Users/cw171001/OneDrive%20-%20Teradata/Documents/GitHub/prompt_wars/config/game_gemini.yaml)
* **JSON format:** [config/game.json](file:///c:/Users/cw171001/OneDrive%20-%20Teradata/Documents/GitHub/prompt_wars/config/game.json)

You can define:
* Board radius
* Turn limits
* LLM provider configuration:
  * **Ollama (default):** Running local models like `llama3.2`.
  * **Google Gemini:** Running cloud models like `gemini-2.5-flash`.
* Bot profiles (unique names, teams, and the core **System Prompts** that drive them).

### 🦙 Configuring Ollama (Local LLM)
Prompt Wars defaults to running inference locally via **Ollama**. Follow these steps to set up and configure your local LLM environment:

1. **Download & Install Ollama:**
   Download the installer for your OS (Windows, macOS, or Linux) from the official website: [ollama.com](https://ollama.com) and follow the installation instructions.

2. **Start the Ollama Server:**
   Launch the Ollama application, or start the server from your terminal:
   ```bash
   ollama serve
   ```

3. **Pull the Required Model:**
   By default, Prompt Wars is configured to use the `llama3.2` model. Pull the model locally:
   ```bash
   ollama pull llama3.2
   ```

4. **Verify the Ollama Configuration:**
   Open the configuration file `config/game.yaml` (or create a custom configuration) and ensure the `llm` section points to your local Ollama instance:
   ```yaml
   llm:
     provider: ollama
     model: llama3.2:latest
     base_url: http://127.0.0.1:11434
     temperature: 0.7
     timeout_seconds: 60
   ```

5. **Run the Simulation:**
   Start the simulation using the Ollama configuration:
   ```bash
   python game.py --config config/game.yaml
   ```

### 🌌 Configuring Google Gemini
To use Google Gemini:
1. Copy `.env.sample` to `.env` in the project root:
   ```bash
   cp .env.sample .env
   ```
2. Open `.env` and add your free Gemini API Key from Google AI Studio:
   ```bash
   GEMINI_API_KEY=AIzaSy...
   ```
3. Run the simulation using the Gemini config:
   ```bash
   python game.py --config config/game_gemini.yaml
   ```

*Note: The Gemini configuration includes `request_delay_seconds: 5` to safely throttle requests under the Free Tier's 15 RPM limits. If rate limits are hit, the client automatically handles exponential-backoff retries (HTTP 429).*


