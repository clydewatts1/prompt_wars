# **Prompt Wars: Game Design & Technical Requirements Document**

**Version:** 1.7

**Genre:** Asynchronous Multi-Agent AI Strategy / Programming Game / Tactical Survival

## **1\. High-Level Concept**

**Prompt Wars** is a spatial, multi-agent AI programming game heavily inspired by *Core War*, *Screeps*, and *Halite*. Instead of writing traditional deterministic code (If/Else, loops), players write **System Prompts**.

These prompts govern AI agents (Bots) existing on a Hexagonal grid. Bots navigate the board, hunt opponents, forage for resources, build obstacles, capture territory, and survive by leveraging a ReAct (Reason \+ Act) loop powered by Large Language Models (LLMs). To prevent infinite context growth, bots must compress their knowledge into a limited "Memory String" every turn.

## **2\. System Architecture (The "Airgapped" Model)**

To ensure zero cheating, decouple LLM latency from game rendering, and support local LLM execution, the game uses an airgapped Backend-Frontend architecture.

\+-------------------------------------------------------+  
|                    GAME BACKEND                       |  
|  \- Tracks master game grid, Bot HP, and Compute        |  
|  \- Compiles Dynamic Rules \+ Player Prompts            |  
|  \- Orchestrates sequential Ollama/LLM API calls       |  
\+---------------------------+---------------------------+  
                            | Writes every turn  
                            v  
\+---------------------------+---------------------------+  
|               REPLAY FILE (state.json)                |  
|  Contains full turn-by-turn history of positions,     |  
|  HP, actions, and raw LLM "Thought" logs.              |  
\+---------------------------+---------------------------+  
                            | Read & Polled  
                            v  
\+---------------------------+---------------------------+  
|                    GAME FRONTEND                      |  
|  \- Renders visual hex board and unit tokens           |  
|  \- Displays step-by-step agent reasoning logs         |  
\+-------------------------------------------------------+

### **2.1 The Backend (Game Engine)**

* **Role:** The absolute source of truth. Handles board state, physics, combat resolution, and API calls to the local LLM.  
* **Tech Stack:** Python or Go.  
* **Output:** The engine writes the current game state and turn history to a local JSON/JSONL file (e.g., state.json or replay.jsonl).

### **2.2 The Frontend (Visualizer)**

* **Role:** Renders the hex grid, bot locations, and ReAct logs.  
* **Tech Stack:** React, HTML Canvas, or SVG.

### **2.3 The LLM Layer**

* **Default:** Local inference via Ollama.  
* **Requirement:** The model must support strict JSON schema outputs.

## **3\. Core Game Mechanics**

### **3.1 Detailed Hex Grid Design Specification**

The game board utilizes a **pointy-topped hexagonal grid** mapped using an **Axial Coordinate System** ![][image1], which is a 2D projection of **3D Cube Coordinates** ![][image2].

#### **3.1.1 Coordinates Math**

For every cell on the board, the three coordinate dimensions must satisfy the invariant:

![][image3]Therefore, the third dimension is always derived:

#### **![][image4]3.1.2 Directional Vectors**

To resolve movement, weapon fire, peeking, and building, the engine defines 6 unit direction vectors:

               \_\_\_\_\_\_\_  
              /       \\  
      \_\_\_\_\_\_\_/  0, \-1  \\\_\_\_\_\_\_\_  
     /       \\   NW    /       \\  
    / \-1,  0  \\\_\_\_\_\_\_\_/  1, \-1  \\  
    \\  West   /       \\   NE    /  
     \\\_\_\_\_\_\_\_/  0,  0  \\\_\_\_\_\_\_\_/  
     /       \\ Center  /       \\  
    / \-1,  1  \\\_\_\_\_\_\_\_/  1,  0  \\  
    \\   SW    /       \\  East   /  
     \\\_\_\_\_\_\_\_/  0,  1  \\\_\_\_\_\_\_\_/  
             \\   SE    /  
              \\\_\_\_\_\_\_\_/

* **East (E):** ![][image5]  
* **South-East (SE):** ![][image6]  
* **South-West (SW):** ![][image7]  
* **West (W):** ![][image8]  
* **North-West (NW):** ![][image9]  
* **North-East (NE):** ![][image10]

#### **3.1.3 Distance Calculation**

The distance between two hexagonal cells ![][image11] and ![][image12] is defined as:

## **![][image13]4\. Grid Cell Anatomy & Ecosystem**

Every individual hex cell on the board has its own physical properties, resource limits, occupancy, and structures.

### **4.1 Cell Properties (Backend representation)**

A single cell at coordinate ![][image1] contains the following attributes in the engine:

{  
  "coordinate": {"q": 0, "r": 0},  
  "terrain": "grass",   
  "max\_food": 50,  
  "current\_food": 35,  
  "regeneration\_rate": 2,  
  "captured\_by": "neutral",  
  "capture\_progress": 0,  
  "structure": {  
    "type": "barricade",  
    "hp": 50,  
    "max\_hp": 50,  
    "owner\_id": "bot\_01"  
  },  
  "occupant": null  
}

### **4.2 Terrain & Food Yield Rules**

The environment consists of diverse terrain types that influence how bots interact with the map:

| Terrain Type | Traversable? | Food Level | Defense Cover | Capture Cost (Turns) | Description |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Ground (Dirt)** | Yes | None (0) | 0% | 1 | Basic pathway. Fast and cheap to cross. |
| **Grass** | Yes | Low-Med (20) | 10% | 2 | Spreads across fields. Regenerates quickly. |
| **Tree (Forest)** | Yes | High (50) | 30% | 3 | Rich reserves. Slow regeneration. Double move cost. |
| **Asteroid (Rock)** | No | None (0) | 100% | N/A | Hard obstruction. Impassable. Completely blocks movement, lasers, and peeks. |
| **Control Node** | Yes | None (0) | 15% | 2 | Tactical landmark. Controlling it yields global team Compute advantages. |

## **5\. Bot State & Telemetry Specification**

To ensure robust gameplay, we separate **Engine State** from **Bot Telemetry**.

### **5.1 Master Engine State (Backend Memory)**

For every bot, the Game Engine maintains an absolute registry:

{  
  "bot\_id": "red\_prime",  
  "bot\_name": "Bramble-Forager",  
  "high\_level\_prompt": "Stay hidden in the trees, harvest fuel, construct defensive barricades.",  
  "position": {"q": \-2, "r": 1},  
  "hp": 100,  
  "compute\_pool": 100,  
  "memory\_string": "Harvesting forest at r:1, q:-2. Safe for now.",  
  "status\_effects": \[\],  
  "is\_alive": true  
}

## **6\. Turn Cycle & Dynamic Ruleset**

### **6.1 The Turn Cycle (Sequential Cellular Automata)**

The game runs on a sequential, randomized cycle:

1. **Gather Active Agents:** Collect all bots with ![][image14] and ![][image15].  
2. **Shuffle:** The turn order is completely randomized.  
3. **Execute:** Run bots one by one, updating the board state instantly.  
4. **Instant Mortality:** Destroyed bots are skipped if their turn hasn't occurred yet in the current cycle.

## **7\. Interface Schemas**

### **7.1 Advanced Context Payload (Engine \-\> LLM)**

See Section 9.2 for the exhaustive key schema.

### **7.2 Action Schema (LLM \-\> Engine)**

The LLM must respond with a strict JSON structure matching this schema:

{  
  "thought": "I am standing on a grass tile with 15 food. An enemy is SW. I should slip East into the tree tile to get better cover.",  
  "action": "move",  
  "direction": "east",  
  "save\_memory": "Moving East into the trees to hide from Hunter-X."  
}

## **8\. Overlord-to-Cell Communication Protocol**

To ensure seamless operations, the **Game Overlord** (engine) and **Cell Prompt** (LLM) communicate using a transactional interface.

### **8.1 Phase 1: The Initialization Handshake**

Static rules pushed once on Turn 0\. See Section 9.1 for the initialization JSON payload.

### **8.2 Phase 2: The Turn Request (Telemetry Frame)**

Sent on every cycle, detailing immediate local radar (limited to Radius 1 for free passive sensor sweep).

## **9\. Overlord-to-Cell JSON Schemas**

### **9.1 Overlord Handshake Schema (overlord\_handshake.json)**

{  
  "protocol\_version": "1.6",  
  "game\_title": "Prompt Wars",  
  "ruleset": {  
    "vitality\_name": "HP",  
    "energy\_name": "Compute Units",  
    "turn\_costs": {  
      "next\_action": 0,  
      "move\_ground": 2,  
      "move\_forest": 4,  
      "eat\_action": 1,  
      "capture\_action": 3,  
      "peek\_action": 1,  
      "attack\_laser": 5,  
      "build\_action": 8  
    },  
    "weapon\_parameters": {  
      "range": 2,  
      "base\_damage": 20  
    },  
    "buildable\_structures": \[  
      {  
        "name": "barricade",  
        "description": "An impassable obstacle blocking movement and lasers. HP: 50.",  
        "placement": "adjacent"  
      },  
      {  
        "name": "collector",  
        "description": "Must be placed on Grass/Forest. Generates \+5 passive Compute Units every cycle. HP: 20.",  
        "placement": "adjacent"  
      }  
    \]  
  },  
  "movement\_vocabulary": \[  
    "east", "south\_east", "south\_west", "west", "north\_west", "north\_east"  
  \]  
}

### **9.2 Turn Request Schema (overlord\_turn\_request.json)**

{  
  "cycle\_id": 42,  
  "bot\_identity": { "id": "bot\_01", "name": "Bramble-Forager" },  
  "status": { "hp": 100, "compute\_units": 45 },  
  "current\_cell": {   
    "terrain": "grass",   
    "current\_food": 15,   
    "max\_food": 20,  
    "owner": "neutral",  
    "capture\_progress": 0,  
    "structure": null  
  },  
  "spatial\_telemetry": {  
    "distance\_to\_edge": {  
      "east": 2,  
      "south\_east": 1,  
      "south\_west": 3,  
      "west": 4,  
      "north\_west": 4,  
      "north\_east": 3  
    }  
  },  
  "memory\_in": "My energy is low (45). I need to secure this area and digest food.",  
  "passive\_sensor\_radar": \[  
    {   
      "entity\_type": "tree\_terrain",   
      "direction": "east",  
      "structure": {  
        "type": "barricade",  
        "hp": 50,  
        "owner\_id": "bot\_02"  
      }  
    }  
  \]  
}

## **10\. Prompt-to-Overlord Commands Vocabulary**

Every turn, a bot must decide on a single command. The engine parses the "action", "direction", and "target\_structure" keys of the bot's response.

### **10.1 Active Command List**

| Action Command | Parameter Needed | Compute Cost | Game Effect |
| :---- | :---- | :---- | :---- |
| "next" | None | 0 | Instantly yields the remainder of the bot's turn, saving raw CPU compute. |
| "move" | "direction" | 2 (Ground) 4 (Forest) | Shift location 1 hex in the chosen direction. |
| "eat" | None | 1 | Consume food from the current cell, or digest raw wreckage scrap to restore Compute. |
| "capture" | None | 3 | Claims or increases dominance progress over the current hex node. |
| "attack" | "direction" | 5 | Shoot a linear laser beam up to Range 2\. Deals 20 damage. Damages bots and structures. |
| "peek" | "direction" | 1 | Perform an active directional sensor sweep up to Distance 3\. |
| "build" | "direction", "target\_structure" | 8 | Construct a specific structure on an adjacent cell in the chosen direction. |

## **11\. Detailed Action Mechanics**

### **11.1 The "Peek" Command Mechanics**

A bot has limited **passive** radar (only seeing adjacent cells at distance 1). To gather deep intelligence, it must use the active **Peek** command in a chosen compass direction. Refer to Section 11.1.1 for line-of-sight raycasting and Section 11.1.2 for sensory feedback.

### **11.2 The "Move" Command Mechanics**

Movement shifts a bot's position by 1 hex in a target direction:

1. **Traversability Check:** Bots cannot move into cells with solid structures (e.g. an active "barricade") or impassable terrain ("asteroid\_obstacle").  
2. **Collision Check:** Bots cannot move into a cell currently occupied by another active bot.  
3. **Terrain Weighting:** Moving onto a "tree\_terrain" cell costs 4 Compute, whereas a "ground" or "grass" tile costs only 2\.

### **11.3 The "Eat" Command Mechanics**

The "eat" action converts physical entities on the current tile into operational energy (Compute Units):

1. **Ecosystem Grazing:** If standing on Grass or Tree terrain, "eat" drains up to 15 food from the cell's current\_food pool, restoring 15 Compute Units.  
2. **Wreckage Digesting:** If standing on a hex containing a "wreckage" object (left behind by a destroyed bot or collapsed structure), "eat" absorbs the wreckage scrap, instantly replenishing 30 Compute Units. Once fully depleted, the wreckage entity is deleted from the grid.

### **11.4 The "Capture" Command Mechanics**

Using "capture" advances control over the bot's current standing tile:

1. **Progress Increment:** Each execution increases capture progress by ![][image16]. At ![][image17], the tile shifts ownership to the capturing bot's team.  
2. **Control Nodes:** Capturing designated Control Nodes grants ![][image18] passive Compute Units globally to all allied bots on the map at the start of every cycle.

### **11.5 The "Build & Destroy" System**

This system allows bots to dynamically reshape the map layout by constructing custom objects, and defines how those objects are targeted and demolished.

#### **11.5.1 The "Build" Action Pipeline**

When a bot issues a "build" command, the Overlord verifies the target adjacent cell ![][image19]:

1. **Placement Validation:** The target cell must be a traversable terrain type, must not be occupied by another bot, and must not currently have an active structure.  
2. **Deduction:** On success, 8 Compute Units are deducted from the builder, and the structure is spawned with its full maximum health (HP).

#### **11.5.2 Built Object Structures**

| Structure Name | Max HP | Passability | Environmental Influence |
| :---- | :---- | :---- | :---- |
| **Barricade** | 50 | Impassable | Acts as a mobile wall. Blocks all standard movement, laser attacks, and peeking. |
| **Collector** | 20 | Traversable | Must be placed on Grass or Tree tiles. Generates ![][image18] Compute Units for its owner at the start of every cycle. |

#### **11.5.3 The "Destroy" Mechanics**

Every built structure is mortal and can be systematically destroyed by weapon fire:

1. **Targeting Structures:** The "attack" command fires a laser beam of Range 2 in a straight line. If the beam intersects a cell with an active structure (like a barricade or collector), the structure **absorbs the hit**, taking 20 damage.  
2. **Line of Sight Protection:** An impassable "barricade" successfully protects any bots or collectors standing directly behind it. The barricade absorbs the laser hit, preventing the weapon raycast from traveling any further down the line.  
3. **Wreckage Conversion:** When a structure's HP drops to ![][image20] or below, the structure is **demolished**:  
   * It is immediately removed from the cell array.  
   * It leaves behind a "wreckage" entity containing raw salvaged scrap.  
   * Nearby bots can now step onto this cell and use the "eat" command to consume the wreckage, recovering vital Compute Units.

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC0AAAAaCAYAAAAjZdWPAAACuElEQVR4Xu2XO2gUURSGd0gERcUHLEvcx92HuIqC6II22khEg8TGwmLBVrCxtBXFQjAggiIoiIIExM7GQlBJGRstbER8IEkRxEoQNInf786sl8Od3Yni2uwPh535z392zj333HtncrkhhlgZnHPH8vn8Osv/Y4zy3AuVSuUU15F19kS1Wj1C8CPLDwKtVmsVSd/k+SesLxW1Wg29e1Eulw9a36BQKpW2ksNLctlnfSFEVPkqAdNcj1rnIEEe5zPNNqI29qlYLJasb9CgRTaRy6zlLSKEdxA+KRQKa61TwDeGTWFvsadMX5OKnCTunNWGUK/XNxB3WzG03xaub2GvsRvyWb20abn8gnYKRM/4w7vWJ+A7pFkgwbPcjqDbzv07bBlrW30Aar3LxB9Gv8j1K2w/12ewb9iEDVAx4Mcs34Wc2IdQ1eB24lvQTGh1J7wGCP8Z2+HrQ2BxFRUfF2eJ2KNJobAv2B4bo2Iwm7st30WPpLV3TmPf8R1IyKTnsJlms7neDwiBpDej3RsnOqt48bpnAButXkAzibUs30Va0qqi61Sz+yDDX/P1/RDHZYr5m6QnXKdv7+e8U8p1dpplFtRxT94X0ivW8iFI17M90hYigxiHXzKDSXaaeX7rMTei9okfknoEq8ouwxoQ9EwV0/I+IlXTmS2v0WiU4d5glxKdtizuFzXI5P3E/Z6Rr2lTqt7HP5P1nUYF7LnlCYhOu8DhEif0HrunQZHUc35/eANJenXedWZl0o9PwF68Df+C5UPQ+nEZDhc9uIb4Y6hPtdUx9QUGtjoenJIbtzr4dlrSINIuYskQNFv815zlQ8jy7qEt8KGq6vWz77vOoHcZfqVQq17EHlhHELU+b3nVzkk4R8KPqdoa36cYfFdy6QPOhOQtzwUOnJ5w/+8jYKryJx8BQwwxxODxE+/8s2XqL+4RAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAAAZCAYAAACB6CjhAAADbElEQVR4Xu2YS2gUQRCGd0kERcVnWLKv3oe4BgWJe5CIXiSignrQg4d4VSEXQUGvXnIIKEgg4iMgChIDih49BB94EeJJUEQJPgjmICEgKKIm8SunJ5mtTO/s6mlhfyhmpuqvnu7qqprejcWaaKIJDWPMUFtb2wqtbwTkcrm9zH8wkUgs17ZI5PN5fM0LrW80lMvlJQRiJJvNnuUxru0uxHG6RACGtaERwTq6kHGCsFnbQgE5D/lTJpM5pG2NCClh1vSETT2vbaGA3INMpFKptLY1KlhPHzLGxq7RNo04pBuQR13NA1s7clHSCnlMvygR3aOa50KhUFgF/6X4kGVJxriOvEYui03zo4DPRuZ8B/9XXI+jatEcbPuRaea6VdsqEEiXm9omwLYbmeBFp3hsgbeJ5/fInOY6IP2lH/9z+MzYQGznvhf5IRPVDtUAvxP/t1x3yOLsfZfm8b4y+m9cD2pbBYy3ux9lgtomTQTbF8kQ6a6+XoKFfirIdSGdTqdshg0gs/ju84OOTMuCtE81wB8SXzuGZKXMb1GzQ1fANomc1rYKVAlAK/ph5Be2nb5SagrdGPIsSHaBAKyFu80ueL4mZQEEY7XmR0AycIRx5mQ8yqkYUbZh66qEi4iuA5kKTlrpB4L8KPyLTxgkpRnnpw3CDHJEcwSudS2Cqwfg2I1+Vg3gN8xJSTGra5EMsc3GefCwAejQ+iDIlg3IMq0X4NtpvJKZb9bc3zfe2aVV0WvvASAO8XZwYEGxWMyge4f0+Tzp4saL+t8aFKXxuu2cfVnZ9w+iVCqtDPqEgQAmjHd4Cd0xu/PfuZ7wdZa/J8jzYflfI78CAhZ20oScA+ziPiC3kFEGfcr1t1kIil8S0mwkW0KjLZ+tXMShRHaeMe5JhmmbQD6X2B7AeYRck17A84GYI+tkjsjzmj6zpspJULq/7A4vXGoDJQvt1jz0Pa4AgHjwK1INvKNf64KwJdvOZq3TNh91nwRjtf0WkK/CXdnt7EL9B22DBHCL0tcNxunVunrBPHYxzhvpKdrmRD7i12DOOwB9ZvEPdaOyL7wQC2lG9UB2VZdhvfB/DTKfM9oWCZwO65pJJpPrJZ2kRHzheVwWLXb7nR/834kLso4GWA8Y4xhypdaSWwTTwH+ISA9i96+6DkdNNNFEE0H8AauY8l2lTvvCAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAzCAYAAAAq0lQuAAADCUlEQVR4Xu3cPYgdVRgG4F2iYBH/MJuQ/bv7B0sqCUsqRUhAsLEJCEKakFKshCAIFioh2CadJKiF2KRTUCRFiDaaQgTBQiQG7EJShFiliO/JzpXxc9fc7NVdA88DHzNzznfPzO1eZubeiQkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABgZCsrK08MBoOb8/Pz36aeq/MAAA+FBJqzdWxcU1NTuxcWFj6u49sp53813+1WdziZwPbh0tLSk39pAgDYKTMzM89ks6s7HG43NEpgawFscXFxX9tv24Shp2pP34MGtrW1tUdzHfvr+Diy3rXUleFxAtubOX6j3wMAsCPm5uYOJZh8nvos9d7q6urjtaev3XmqY1V6vkwA+yp1PPsfZd2rtaevhbr0XKzjG0nfkbZe6nzWfr7Ob1W7u5a61Ds+ljrVawEA2H4JJD8NQ0q2R1N3S8vf3O9O2PT09J4EqafbHar0vpR6P+v+Vvv6Mr+/H5b+SfrupA4n5D2bc7xY53O+x7r1Nqzhnb8qc7/3ryFrv3y/7woA8J9rAS31erd/JnWjP9+Fn5OpD3p1tRzXR5PtkeojGb8wOzs7U+b+VNb4JHW9P5Zg9UL9TDNYv+a7ubZ36tw4BgIbAPB/04JW6pfhHafs30idq33VKCGmParMWnfq+Ga6a7lUx6vWl82uLkh+n/Os1Z4W9Iahb7Oqn2kyfiV1bXjcvcN2tN8DALDdJltIaY8vsz2QutUeM9amapTAlrUupH6t45sZjB7Yfm4/OOj22ztvk6Vly7LewdTNtr+8vLw3+z9O/IvrAwBsSULJN6mvE8IuD8Nb7alGDGw/pD6t45t5gMD2Wjt/q1zr6To/pvZXHq/kHKey/nfZflEbAAB2zGD9BwfH6vhG0neijo2r/a1H1n2rjgMAMHEvgL07WH+R/3bq7ToPAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAND8AbpUm3p6lfgBAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAzCAYAAAAq0lQuAAACLklEQVR4Xu3bsYoTURQA0Cy7gqCCojFsxkxCAqawEdKJP2Bj40f4DVrZ7DcIiyAWVn6AFlus2gjaKIitLIKljaWL3osjxMe64GSNGzgHLnkz7+a+vO7yZtLpAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADwn4xGo7PD4XAzhmvl3LLMZrMT+TtyPJ1Oz5TzbUwmk4vxsR51Tzb7AwBYPb1e71Q0M28jtuu6fljOL8l6rP8x1n8en1sRd8uEvxW1rkedNxFPI15FPI57V8o8AIBjLU+yopF5madbcbnxp4YtT6cOi84CJ3ODweBm1NhvLteaxmr8W1ILUeN+7ifqfWlO2J5UVXWpzAMAONaa07WdiK/R3DzrLNB4HSTqbh8WmZPrZlOV436/fyHG77PBmq8T11fL785Hzs/np2ZvryN2yzkAgJURzcy1iM181yuanjsRj8qcsFE2SAdE6/fD4rvfIx7kONa/nddlTltZK0/wyvsAACujruu9X6dT0dzcivGoSPnnYt0PEVudn49D9yN2ypw2Ym/notZut9s9Xc4BAKyM6M9eZFOTEeN35fwyxNo3Ij41v+Nb07wtbDweX4493SvvAwDQXp6wfT6KPxwAAHDEqqo6n++bZeRj2nIeAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFieH8ssZ2mX2IDpAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJsAAAAZCAYAAAAmGVxfAAAEW0lEQVR4Xu1ZT0hUQRjfhYKif1rJ5u66s7ssLVKXWiKEukRBHewgQoHRJSro2EXoFIGHbiFRRIJ0iEg0BJGQOgQFRV4isCSQIiQRKSFQEkv7fc5Mzn77Vn3bvvfcZX7wY9988828b37vmzfzZkMhCwsLCwsLCw8QFkI0ZjKZ7bzCoiRYPZ2Qy+U2QpgecBGcA5u4T7UimUzWYLwt4EdcP+D1paAa9ETMx8DP4AXwHdgZiUS2cD/XaGhoOIrOniUSiSElUA8Jxv0qBUiaTRhDW11d3VZeZwI+L8FR8Ak4X65kq3Q9Efc+xDyJ33NUjsViu6DNW/AWimHm7g7ouE/I2d0k5EycI8G4X6WAkowSB+Oo53VOgKg5+M6UI9ni8fjmStcT8XaC40iyuGHrIBuYMn1dA2L3k0i43IDOHokKnI0mgkw29HWikvVE7LWIdRgcS6VSEcPersbRYvq7AokCkU/qshYe/EPCmb4mqB3qzwu5no+ijzMILovfe6jbyf39hBKsN4hkQz99bvRMp9M7UNeFNu9JQ7wBoyjfBz+Ad6iet/ESiDGN+06AL8xtCMpXwUVKOtPfFUgYNQs1aDZ2UcfgAKtbAtrsQd1zEpYSSyXsYxIU7KU+eBsCklEg2FY3pDa8n9WAGOpJLPrldU7QCVGuZHOhZxj3vElJSA+R9FNJdxjXV8Bf4CnDPw9e6Km1IP3MZIO9mcZQskbq7dTP7cYNC2aj2pMMgGO4cVLbjWAuG+558EIcJ4iAkk3pWfD20v1zPeEfQ7mbHqqQ+6QFmvyqTPFPgwfMvkx4oacRa3mTTchNbB+3h+QZ0W3qXLDZiJudVfYOswGVwVksA4dMu9coIvhFxDJKvw51BYJrgUsWUoH0dFoJQkX0pFUB5YNGcg0jllqqU/vOmvxuvIcnyaYGOFjsKwn2/ULOrKXZpu3UBpzHzY9oW1IeNZB9JBqN7tZ2P7Bekk3rye0axfQkwNYIfgc7TXsQMGLhe7Y2ISfLNdN/VayWaBoJed4yZQqE6xEeCPo5rQJpW25diCKJsSJ5YqwFoszLKL2JwAy3a5Sip2kXcgmlB9xo2leDR3rqt/AE/NPaWGqMein8DY6jw6/FSPVCbvoXhUowITe7/1739BDQ3yfYZmDL8XsFAeEy2Wjph+8s+BDFgkNLIb/EvtAei9cRStFTT9ZsNrtNyMPlvAkcJOg5Ip6fCXaoi/LdUJGPP0eoT+03NGCXXABb6KAPv6/Ap0n5Bfoa/CaMBAwaYo3Jpnz0+PKIsTRrP1wfh+2H02T6Dz2XzqvQfi+up6DlddZ1kAgn5LHWpJpIgygP0R6TO/qBsMp2+l9x3ew3NMQak80NIHa7U7KVAWF6iOvxwJcmEsbcShMi5PDG9x1ieeO44n7NT9ByBJEulXNZQn/dKeNE3cJnqDM3Oqmfpq8tXl9NwBivcpuFT0jKk2++Ab7B/aoB9BHk999GFhYWFhYWFhYWFhYWVYW/5SD7sFjSCLEAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJsAAAAZCAYAAAAmGVxfAAAEXElEQVR4Xu2Z20tUQRzHd8Gg6GYXM2876wVFKqK2CMPeCpIoIqQEo+gp6h/ovfChIAKLKLKkh6hMQZCIUigwSAgiohuBD0XUg4QQFEmlfb975ujszz3rrnvxbM4Hfuw5vzMz5zff+c3MOWcDAYvFYrFYLFkgqJSqr6mpWSYvzHOiukinZZZEIpEFELQLNgEbgzXIMn4mHA6vRcz9+H0EO4rjoaqqqlpZLlWELnmlSboUFRUtqaio2IF+P+axvD5rdKP9oVDooRa2i0LLcn6kvLx8EeLtM2PG8RnY6+rq6jWyfCoIXfJGk0RgMh6SPpPi4uLF6O8d9HcYdg/2JKPJhgZ7YAdgDcpZ2cYotCznRyDMTsQ7zvgNXyP7AGFbzLKpoJM4Rpd80SQR6MdF6fMCZUsynmwYnF6Ki8MCNH5b5dHqhjjbdLxNrg/9ieD8B+wWToNG8aRBG7uELnmjSSLmNNkoJlaA3e65MVB/KbhZ1oT1cP0Iyr2EvefyXFlZWYffq7i2UpbPEkyCbsbLuF0n4tgI3/fZCuWuaqYuM2mCZ8TluN5BHbACluL4Guwt7DKvyfJzBPW6Lp1eqEwnGwXVs9eFAXUoZyb3iWtR9AP5AAeEiaUT9i4HA9bNNmQdgiRQGKzmVIx1ZDsuFIFiKJFsWqSP2krMOslATXTfJvs+gyZB1DnLRKQGOH4F24bjk7Bfylh1BXzT3S77nMhQfg+fq2RDyUC90Eav9HuhdcxMsunVadrNOXDKYyYbD+TDEDTs+lFuLwcDruNG8RjyIdlcTWS/2X4CTcrg69TxjDNZjdhGYZvM8gbzJ9mU8/DbI/0BR4RLKs5MhpAt2t9mVuA57Ce2kK2mP5tkI9mU1iTe6qU8NOHqDt9mHc9zxLKCfp5Dr8KpJnJDaWnpatx3v0xU2GHE9yKOvxl92CDb0Tqmn2xamPteb1jwr1fOrIzOVNfPOrDfCLDR9eH6Qu1/w466/mxj3Dcm2XBcBd9X2GBdXd1Ss04iZquJC/z1sHbpzzW+SraZRHVBEOtQbsQUlwklA0A7+5Qz41unak8n09soYVyMz7x3SH8OMbd0LVyT1z8k6WjiAl+7Su3fhv9/G9Vb4R/YZ9z8k5fxunIe+ifcmyrnQXlyq8CMqEF7H5RYXXKFsZXKj7rvysrKynnOwVHOC80EYuwMxPkcko4mrM8VFOeDaQ1Mlkk12agf+5TK7hCDfkUf0mKlYtEPpzqAp7AHYecN9BnsizISMNcoZ/viZ4YbIWf2MyHMv5e4gpzXfRiQCZGuJrqNWhyPmO36jWSTDeN6M05fOVFPybK5IIikW4WgCpUz0N/UHD+rcFXDFriFyeb14ZWTAXZBJluGCPJFQTr9RLLJ5luQZK068xM+r/kB5fztdC4QZxudJxRggTgmnXmB/ubGL/ijfFOT1/0EVzvM6ivK+5uXxa+EnS/m8uH5tCznFxDfQcR8IjB/VzWLxWKxWCwWi8VimTv+AbAf5w5MIKh0AAAAAElFTkSuQmCC>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKsAAAAZCAYAAABO6t5nAAAEfUlEQVR4Xu2aTWjUQBTHU6yg+Fm1Vvuxk7YLpah4WEQEBQ8KetCDCAoVb34cPOmh11IRFDyItgelUDyInwVBxE+oqKDgRQ9CEQpWREER8aBQtK3/fzNjJ89s2u0u3ex2fvDIZt6b18w/L5NJUs9zOBwOh8Ph+I8KpVRrOp1eLB2O6QE9V/tAtjvyIJPJzIWwN2BjsGHYJhlTrlRXVy9saGjYgjG/gPVzX8ZMh1QqdUDrOYZ67ZD+csbWtFB6/kMnfgSBH2iBb7CAZVw5UVNTswDjvYaxDsJuwn7CnhRC3Lq6uuUo0IfI1631/FRfX5+WcaUExjMP42iL0ydK07j4aYGkfbA9sE0qmFmHWcAyrlzBeFfDhgpVrDixR5HrEosW25cqKNiTcFXI2FKBumBcl6mV9EVhNC2EniFwNdzGlT8fPyvxB65qcct+djUUslibm5tXIk8/Lva13McJ3q/1LOnZNRHFyiLFQeww+yjcjApuiSP4vd2OtWE/+A8i7jVsADn2NTY2tmB7UcYmnUIWq55VL3h6FmU+5mXBwndOhJvnhU7YW9gJ6LoMcafxuw8zc72MLxY411U4plvUSvqiMJrmq2cIFqqeVQ2cXXsoLuyO8I2DPqvge0xBKa4u+OvYH+GAZLwBxaww6L25GPvIPIXGCKvyLFYcaw1y9OO419jtKlhijcK+2u0Euh2hoc8uHTOEWXk3tj9gx2W8TW1t7QqpV5zhPK2TOaaK1ogXXXGKVc+Ot2V7KmZ2ZR+034ENQmTftGuxOXscscJDlHuxov8xPXuG1qb27Gr72I4x9kLTOupGP3PQR+1ZtP+SRDCrilUFV3yfbPeCd65dWrzQ7OpPrMFO2R24D/sFgTfY7TNAJY5pqzwx2YyxMoERVuVRrFirNiD305SYVQ3w7UD+Uduv70gbuRRAey/8n7Ftoo8PZ14RHshiJpRDOL4BbqUvakIxmk5XzxD6ar+b7amfDwjwf6fAFJptfvD64i7sNw5ys4m12t/yap/IMiMkoliRu13FPPHru9h9xHR5IoaaUTtqSC1t30yTuGKdrFANOJA1iPuqdMFaooZOql5jjcHa7P6SGCGyWpQQhcYIK8elmYPj2IzjWO9lKUSiYgrVoJdQ1ClUsH6wBBjF39lmhU/KrFgG+MGt/A/sIwbxIZvRr4KHJgr8xJt4+HoFfxVzQYA08r1D20+0ZcJ/qTTgU7ce67OWlpZFtg9tO/X4s44PvkbYF6lflEXk4pLrCuw9166hxAlC5VisRlOpZ040NTUtURMvqnOxUfbXB/Ecds8P3gDwM+UnZRVwqeAH7w3lOMcNY2lnDH63wj6rYObbJXMQ5OmQ/adgPehaqT8cvIFd5b7MnRTUFIs1m6ZGz2JQoT8pLlXByfwGOy+DygmMry1bseYLdfSLvFadjKkWa6LhSdRXT+x6tcTh8qfbfJWajejXbIfzXoMWC/3AwK8a38v5ROp/9DnrJfg27YgBt60zEQ8PnTKu1OEXOs6qSfr06XA4HA6Hw+FwOBwOR078BQMU5HhdjDWHAAAAAElFTkSuQmCC>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJsAAAAZCAYAAAAmGVxfAAAEKElEQVR4Xu1ZTWgTQRROoILiX6uWSJJmkhAMQS8aRAoKIgp6qIdSUKh48SB47KXgSYQevEkRRSwUDyKWVgqlSNFDQUGxFxGqRSiKFEspWhBaLNXW72Vm7OQlMex2N03CfPCRnTdvZt98+2Z2dhIIWFhYWFhYWPiAoBAik0qldvEKC1ewehZDNpvdAmEGwDVwGWzlPvWKeDzeiPG2gx9x/ZDXu0E96ImYT4GfwSvgO7A3FApt536O0dLScgKdPY/FYmNKoAESjPvVGzDOl+AU+BRc8SrZal1PxH0QMc/h9xKVI5HIXmjzFryNYpC5OwM6HhJydrcKOROXSTDuV6+AqFmMedGLZItGo9tqXU/E2wvOIMmihq2HbGDC9HUMiD1MIuGyAZ09FjU4GzcCL5MNfZ2pZT0RexNinQCnE4lEyLB3q3G0m/6OQKJA5LO6rIUH/5Bwpq8Jaof6y0K+z6fQxwUEl8bvfdTt4f7VDC+TDf0MOdEzmUzuRl0f2rwnDbEChlF+AH4A71I9b+MnEGMS950Fx5ubm3doO8pd4BolnenvCCSMmoUaNBv7qGNwhNXlgDb7UfeChKXEUgn7hAQFB6kP3oaAZBQItsMJqQ3vx2vohPAq2RzoGcQ9b1ES0kMk/VTSHcP1NfAXeM7wz4MfemotBEs22NtoDK41UqvTMLcbNyyYjWpPMgJO48ZxbTeCuWq458EPcbyAHq9rIRWUngWrl+6f6wn/CMr99FCF3Cet0uRX5XFwATxs9mXCDz2NWL1NNiE3sUPcHpBnRHeoc8FmI252Udl7zAZUBpfwGjhq2iuABsR0kotaiuRLbcwOtMCuhVQgPYu9CQIl9KS3AspHjOSaQCxNVEc2xNOY343/8CXZ1ABHS30lwX5IyJmVm23aTm3AFdz8uLahfquyT4bD4X3aXiFURbJpPbldo5SeBNgy4Hew17RvBoxY+J6tU8jJct30L4tyiaYRk+ct86ZAuJ7kgaCf8yqQzvXWhfBj2fcC5ZKNViIwxe0abvQ07UK+QukBZ0x7Ofikp16FZ+Gf1Ea3MepX4W9wBh1+LUWqF3LTvyZUggm52f233NNDQH+fYFuELcvvVQugVz/iXwIfoVhwaCnkl9gX2mPxOoIbPfVkTafTO4U8XM6bwJsJeo6I52eMHeqifC9Q4uOvKNSn9hsasEOugu100IffV+CzuPwCfQ1+E0YC1gqE3CfxceaIsbRpP1yfhu1Hscm0AT1z51VofwDX89DyBut6MxGMyWOtOTWRRlEeoz0md6wEgirb6X/Fqtlv+AmI3V0s2TxAkB5iNR740kTCmDtoQgSKrPgVh1jfOP53v1brgOj9CeNE3aLCUGdug+ACfW3x+noCxtjFbRYVQlyefPMN8E3uVw+gj6BK/21kYWFhYWFhYWFhYWFRV/gL/CHjyXz/cgAAAAAASUVORK5CYII=>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJsAAAAZCAYAAAAmGVxfAAAEKklEQVR4Xu1ZzWsTQRRPQEHxq37U2iTNbNPQUBREo0il3hQMogcRLRT0KPoPeFd6UBChiCgWiwdRawuFIqItKFSw4EXEL4QeFNFDkYKgWNTW38vMtJNnNm2STbpr5wePzL55M3nzmzdvZmdDIQsLCwsLC4sKICyEaEkmk6t5xSJHlheutCgR6XR6KQjthUxDJiGt3MbPcBxnE3wewu8jyAmURxOJRDO3KxaMl0BxUi5qa2tXNjQ07MG4H1OZ15cM1elQPB5/qIjtJaK5nR8Ri8WWw99B02eUz0FeNTU1beT2xYDxEhhOykFdXd0KjPcOxjsGuQd54mmwocN+yGFIq5CZbZKI5nZ+BIjZC3+nyH9D10ZjQJZrN22LgQriHF6CwolXwJjrPQ82TM4AkYviEnR+WwQou8HPTuVvRuswnjSev0Nu4TFsmM8b6GMf4yUwnHgFz4ONyEQG2K+fjYn6Q4SbtiaoHeqPw+4F5B36ONbY2JjC7zXUreP2FQIFQR/5S35rJfzYCt23UonSWc3kZS5OcEZcg/pu4gEZMILydcgbyBWq4/ZBgPA62IhQtXo1aAK7hVzJg6wuC3UgH6YJocBSAXuXJgPSR33wNgQEgcBkHSlGqA3vR4NIIDIECzZF0gcl9Wab+YA4UWObGfscnITR5jwFInGA8kvILpRPQ34KI+sy0Jvubj7mQgL7A3Su4h1VAopHb4JNZacBrqeJEy4r2TiQj4FQR+thd5AmA6qThnkOghBsmhM+buq/ACdR6HqUP1MUrIZvE5Btpr2BxRNsQh5++7k+JEm4LPKsZBDZrvSdZgN6hvzAFrLT1FcSlQg2oTjJl72ECyeU3aHbrvx5Dl/Wkp6ewVfNbBfVA2VWHqhuAp8zecbrXbApYu67vWFBv0XIVZldqVpPbSC/4GSb1qF+mdK/jkQiG7S+0jD+NyfYUE5A9wUykkqlVpltCqFUTjSgb4F0cf1CwDfBNhepGnBkM+zGTXIpoLgD6OeQkCu+Y7b1v/B6GyWQX+Sf+d9xdR3iGFu6Ii7j9oWkHE40oOsSxX1t+P+3UUduhb8hnzCAj25C9UIe+qf1nwp5UJ7ZKrAikujvvWDZpVowtlJ+qfs2Go3G6JkmR8gXmmn42BPKcx1SDifUnjIonkfKmhifgfijMRWzO+RAvaKPKrKKkezFqXLgKeSBI99An0E+CyMAqw0hty+6ZrgRl6ufAsL8vEQZ5KIawzAPiHI5UX00ozxu9htUYF5v5hkrLdQz3LYaCCPo1sOpGiEn+qtY4LMKZTVsgTso2NwuXmkxQC7xYPMIYXpR4EoLD4Eg61CRX/C85gcI+dnpQijPNmrhc6g7N7rBn6A3NV7vJ1C2Q1a7KtzvvCz8CkfemPPD81lu5xfAv6Pw+VTIZjULCwsLCwsLCwsLC4vq4y+7yNheVrcXAwAAAABJRU5ErkJggg==>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKsAAAAZCAYAAABO6t5nAAAEd0lEQVR4Xu2aPWgUQRTHNxhB8TNqjObjZpMcBFGxOEQCESwUtNBCBIWInR+FlRa2ISIoWIgfhSKIhUSjAUHET4iooGCjhRCEgBFJQBGxUBA18f93Z3Kzz9vLJZdks3fzg8fezrx5N/O/t7Mzu+d5DofD4XA4HP9RoZRalU6nF8oKx8SAnit9IMsdRZDJZGZD2G7YCOwnrFX6lCrV1dXzGxoaNmLML2C9PJc+EyGVSu3Veo4gXztkfSljazpZeo6iAz+CwA+0wN1MYOmXFJAcczCG9nxC1dTUzMN4r8OvH3YT9h32JF+bQqmrq1uKPjxEvAtaz8H6+vq09Cs1cmk6GXqGQNAe2E5Yqwpm1p9MYOmXFCgQkuUqxrFS1uWCfrCByUpWfPchxLrEpMXxpQoS9jiqKqRvqWI0nQw9Q+BquI0rfy4+VuILurS4iZ1d40zW5ubm5YjTi4t9Dc/Rjz1az7KYXQ1TkqxMUgi61ZwjcTMquCX+wecttq8N26F+H/xew/oQY3djY2MLjhel73SDflWhT7fiSFY9q57z9CzKeIzLhEXdGeFu9gudsLewo9B1CfxO4nMPZuZ66Z8UjKbF6hmCiapnVQNn18sUF3ZH1P0DbVag7jEFpbg64W/g/A/slvQ3IJkVEmnXeIxtZJyx0EIxQaY1WdHXGsToRb9X2+UqWGINwz7b5QS6HaShzXbtM4BZeQeO32BHpL9NbW3tMqlXPsPvtFbGmCqMpsXoGULPjrdleSrP7Mo2KL8D64fIvinXYnP2OGi5hyj1ZEX7w3r2DK1N7dnVrmM5xngFmtZRN9YzBuuoPZN2NEgOyipZVXDF98hyL3jmel6LF5pd/ewa7ITdgOewHxB4vV0+1URcAPvRlz4ec9TtkjGMsKqIZMVatQHaPE2JWdXAOxjiD9v1+o60gUsBlF9B/RCOTazj5syLZ0NWiT5tkppFGX3ZRgYxmk5UzxD6ar8btevnBgH1XykwhWaZHzwSugv7hY62GV+r/C2v9myUqWemJCviHlN5dvz6LnYfPuc94UPNqB01pJZ2XQzMrGQdK1EN6Mxq+H1WOmEtUUM/ql5jjcDa7faSiMTKazNgGTAL/WhDP9Z5EYlIVJ5ENeglFHUKJawfLAGG8T2bLfcxKYtlgB/cyn/DPmIQH6KM9SrYNFHgJ1528/UK9VWMBQHSiPcOZd9Rlgl/UzxooQpOVu669ViftbS0LLDrULZNjz9yfKhrhH2S+uWyHLG45LoGe8+1ayhwgjGaSj3HRVNT0yKVfVA9Hhtme92J57B7fvAEgK8pB5WVwHGjCkxWP3gWa49x1DCWY/TB51WwIRXMfNtlDII4HbJ9AXYZTSv1i4M3sC6ey9hJI0pTo2ccVOhXiotV8GN+gZ2VTnGhCkzW8YBY7VHJWizU0Y9/rVr68EfUV0/e9ep0oh8JHSh6vZSFy58L5q2UI4HoDQPfFH0t5R9S/9HntFcCt+myBLetUzk2D53SL+nwDR1n1SS/+nQ4HA6Hw+FwOBwOR5nzFyxF43xHjW/tAAAAAElFTkSuQmCC>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGcAAAAZCAYAAAAsaTBIAAAEuElEQVR4Xu2ZTYgdRRDH57ERFL8ScV2yH9Nv364u0YOJiwZBL6KGHPRgIApCbuLHTSQJ8aImBIIYlRw0SIIaEFEElVX8YA9iQMRAdCHBQ5JDQjB4UDAYIYiuv/9Oz3v9amfmzfuIl8wfip6uqq7q7uqu7pmJogoVKlS4LDE0MTFx58jIyNVWkKLRaFzvnDtYr9c3WNnlDOZkZxzHW3isWVnfGBsbG8fBz9AitNHKQQ3n2wjKB7Ozs1dYYYUoGh8fn2buFiYnJ++ysn5Qw+ir0L8KDkF4yCrAuw3ZKehuK6vQAov3ReZojkBdZWU9gVR2LwY/JgDv+OBstzre6TfDw8PXWFmFFpi7Webpl4EsYn+GzDH56xUUn9aeD3Xgr4J3xPIrLEcwV7utrGsQlKegl3isUT6p4FC+G+r41XDeZZ9FTZBrZ9A9g977BD2mfI76ZqvXLeQXOiq77PJRyk308QcRPh+0+v1AlyH6/AI+Fij3k55usDqdQNsD0HzRxaoj/AH2xdTU1E2q66xRcKCPqK5I9Tz/goLUbNwOXRa2oPOrninvg36HLsK/xyp3gzg56w4QlCnK09Bv0Cv0/WbK7/qehABK2fj7iqDvoDrE8ydK51avE3wGUl9XW1lpaGUw6IeD+v0uuRS0nS2dnCF/ANk/flBLg5QN6Pjo6OiNVr8bYGOr+ki5RoHB15c6bNOFRPlmFCykfuCSHXo+XYQ8/63MYvU6gXaPyw67+nYrKw3XSj+rRXRkA+VfdlKLguPPrO+hc+g1vH5Ddei9KLj3Y3/l9PT0dc3GJYCNO5RafIAWNXAvGlIfw2t9L/ZD0P4x7+MktJtxrIqWv7fUyDQThtcGv3CKMk0xlMowcBYDZ1JyyS1DnWsLRFFw4tZua6bClKczTDzVof3eX08dpu0+l6S0NVYWeR/92Bf8u96CnwPRW2nwWSBj1J+BfsTH27ZtiL6Cw6Stp/Gc5cetm0ab4SJnCoAGIh3Vg5R2RPZSPZfszp+ybHjZxrxV73xKg/ZZWYg8+0KRD/WZcXztTCqifhaaDHWxv71uLkwW0nE5i7kQ/iDVxD1hZTMzM9ciO+zMi6g+6cD7U4ML9QVNBvwLzqcbOr7Dt9fqaqYEPznLJk+HOfz5rDYpkD0ieXg+ZiHLvpDhow2+b3rBPpSetdoxjOX1yPSnTHAkl7/SFxV9UnDJebKYUirD2JXUPw9lnpZWknI7z8dd9nuObmfa7idc8s3tW982PRuW4HKCEyXt97okNc5nveR6+bJVbJFjX2jzYYVArxHPIjsGHfR0LOstv1NwYp996j3c8nqGnLmCLwQKMIEccTlng8sPzhI0KOi1LPuyDa20fIsi+0Lqw/JTaLdoDKK874clgjO4LwRlEZf8tqZVI9JEGH5hcGQXejnKSGtlUWRfCHz0jA7B0Q7dBX2YF9xLhVJfpenYReiNDH5ucGQvTm5z66ysG+TZFwbloyg46Vfpfn30BL3T0LFPoUetjE7f6icnvZYfRf8WpSSet0KfuSTnH4a3x7TdDO/pqMddE/ho2rdpcAA+1rrkLNIt7A8FyAUXJAWf+iFoU9juf0X1sy0bzMne+FL9bKtQoUKFChUGhP8A2ouJ0knFGecAAAAASUVORK5CYII=>

[image12]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGgAAAAZCAYAAADdYmvFAAAFaElEQVR4Xu2ZXYhVVRTH7zATFH1aTcN83X3vzNRgBRXTl2QkpsQ8GCUxBIoPBpV9EDhkFERl+JAhWtiXTIgPNQVCD1JBDFb6IhjFPEiRBNNABkoOCAoGOv3+c9auPdtz7r1nJiXo/GFx91lr7bX3WWvttffZt1QqUKBAgQINosk59xS0kXZLLPy/olKpPIBP3mlra7s0luVFc29v73UYOwpNlcvlxfy2i6rVKj/uGegkdKy7u/v2sCPyO+GPd3V19YX8AgkGBgYuIlCf4tMNPDbF8lzA0aegzzF4cYpMQZoO5QTlEp738PxqpF4gAD5aBP1CkG6KZbmgAGDkhZgvIFtlAfqmtbX1MuNp4CP0GYj1C/wD+Ut+m28iax85i7OXxQK/UixAw55PexO0v7+///JQv8C5MF8dxL8LYllD6OjouBYDEwSjM+QrOET+NQWP3zdUU8X3WQGNhPoxmNBOaBK90Z6enrICzPNQrJcXzOVWaB/29mL3BmzeY/MZh9aW5lvvA9g+sg6730Gf0a7EOvVAv0Foij37lljWEOxg8ANjP0r7EdqPQR/KufB2Ybg/1HfJIeLXrJIImpCt4VDxoNroLoWOQ6c1VqycB3agGcV2rwVFB5iPoSq2P+H3MPNti/vNES3YfA+bI1ZJtmhs8WPFWtA2oHnyuyKWNQQ6r4eed3Z6EzGh6/l9EzoBDfvVI9QbEP5y5GdKlsnBijuk1Rqp54KCrrnaqj8E/aiA+DmRUF/5fXK+UMbr/f170j6G/W2lnCuU/j30/R1aH8saQQsdd2dktmSj0DQTe9IzawWIknMlsgOakOcFE/yolLxck0oF/Pul/3fnBoCNhSrFfg7QJhM1dXZ2XlOxU6bsyr6VpFwO9XDJQeg0dBQzb8k+7OZApVnzQbbEj5sGV7/iZEMvS+eJrMyWUQvQroCXGSB4y5CdhXbHPGw8oZVIe7NLVq0+cBXI3A6ULdmU7VgmINteSUr2t7S/zJsIgq38L/T+RmPejiXiDuw/zu9L0B/QytiG4OYTIJecMKZjvsAL3uXsI7UcnONrDWiO05F9JnhBeZs5xSC/W/aUdZJbsAdDG2Z/sK+v74qQ7xGUt9TvNnPeFrWzDjTaUxh7ecZHtt97psO50Z6CFqmNfIj2b35/1vvyfCLtIGDvmJrQNRFM/mTIV5ZjbLUZnaTu3xHKdbRGtj9+acFPBlrFYzMOfFEvCn9nKWWlSA+q+mddjfA8VquP5oP8VFqCxCgn5fWIVlPId8kKnoYmQr5gfvnaJb5pN7YOO3sU2FnKBpck+oG0lVoreKmoJlc0ujnQBLNoAsMbsrIY+dsu/TvI380dlrySHIdlTwGbBdsz9kVs9ddpSWVyLG3Dh7/WJXvDTDbXgGy9rvIcO7aclN0/oeMh34M+D0E/qy86O6CD2Lg61hO0CpGPo3tfLBNcjeCdN8g5rsZNgkqP7TcKpOrzwlBu3xfb6L8m5HvAXwBtTQuQ+pqzzlldIRhzJWN8UOvCss4q9PeU7WmlVLByqmP+0lgm/Fs3CbnRyF2cnKzME6nt+VZCn/Mv5et4CEuAzaU6QciCbGsMS4SrtGJiHTvpqYzOCVaON/rkw9biavQNRjm+F/lPGXvd+YWVyszbbDnJJaXo3YCtsvM09DDUzgvc7F/QwwL4PvzbQn4e0PdlSmgXc3TYehZanaKj/W9O3yY2x1csALr5ly+2h6dhf5vtgiuyCw05exgaCT9kBSZ/IzTpCZ3vdS3DhJfQPuOC/S7OOvSH0FtXmuPq0d4W2jeadVJUUjHO1rnuCy65bYnHGAvLqZJCiRb75kKj+MMuBQRmRb39r0CBAgUKFPiv4S/uSayFXaoRVQAAAABJRU5ErkJggg==>

[image13]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAzCAYAAAAq0lQuAAAK0UlEQVR4Xu3dfahlVR3G8XvRwOjNXqZpZu6cde7M1DhYVAwpipSIgdILNhpGmghSU9GroakUSDCQ/4lEiWhTwmThpIhvY0jeHJGyIEas6Y+EGVCHEhmSRsyaOz3P2WudWfd397nneF/GO/X9wJq99tpr77323uee9btr731nbAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD439fpdC6KKaW0KtZb7tTmx2JZrdvtnq5j2xzLBxiP58RJ2zi5VJicnDxNKdUrHW82b978Oh3X1WVex/fTevlypTZ/IpZFo9R5rfnnbMWKFW+M5bVR6iwH9c9W9bkar6oAABZCHcJtSvuVDijdktMr6rwvHstfuO4wVPaAvoTPDasvCxMTE69Xe78Yy2tq/72jtn/lypVvUP2dSofztJyX6XXr1r2l1NM+7/G+63WPJz5ndfsJ2I6tUYKxUeosB/GXIbX79yr7aF0GAFggfbF+O3bWKtvugKXMq2N/37DgRPV3xLKl5gBK+/1tLK+tX7/+naqzV8e4NS4bRPXPVzoSyrYoTZUO1Odt2L6XK52L69X+XaGMgO0YGiUYG6XOchADNn1XrFHbn67LAAALNCBge6t/S167du0nNXuCgx7VOaks9y1B1blIy1d73sFcDHBkvNu4wP/UC9wReblvn2hbK+tlLnd9d7pl+1W5t9Vvh7azze2s6sygbZyamtE1B1c3xeWDqO7DSi+Esud83GV+9erV71DZn+o6i6GcEx+n0sn5XFnvOsQO3PV8LerzMoy2eVDrnFWXdWcHbONr1qx5u6YnbNy48U2ehuWLKh+zbzvPuZ9RgrG6jrebz9m4z9/YkO0vhPfj6+d8y+d6hlGCsUF1ys9PLF8CrZ+5KAZspmu5VZ+fiVgOAJintoAt3xZ00OKAaErpSOkElf+Y8l9wkOByj75p+nfnczqU6z2g7T7pusr/Vfl3lf25nua/pOn9Sn+ZrJ4HS81+92v5NzT9p4pO9Eia1vu55q9QeklpS67r9XeWdSMtu91Bp9sej3EuqblFXALBceXP0fpPzKikduV9nxjKF8THnprzs7XTjHTuVP4GTR9MzS3sl0tdH5fmD+Vr8ZKml+VtHCkp1+nlS8er/AGVryvbsXh+fO1U7z6le5WmctC2JLT9r3j/atNvlB6Ky2vlcziXUsfBk7Z9l9Lz2v49mj6u6Y2x/mLw+VTapX3s0T4uV/4nnTluC6YBwVgt1vHPZf5M3OLpsFHvhdJ+nsqfgYG/FFmnJWBT2VlOsRwAME+dloDNXFbK3QGWTlBf3k/nkRfnzy/1UxhhU/3Pa/0LnM/PwfVHo5SfcgeX86vKfpS/wu1x3p2Tyq8dawKmf6U8Qqbl5yo/nevvL/Ujt1HLP+i8grYPeZ/DOsjCx6J0STV/ptLjdR3zvt3+WD7WtHnVXCmuUPO5Vp1tZd7tKXmfq7K+Atn3KP/dap36GrgN00oXatnNVXnv/MdzUX8GtHxvFdz5VnD/XCy2HFCXa+g2H5hRISifw7mUOjqmG5TfnJpfIrztFzX/tVB9Ufj8dZqR6Wnlz/O+9YvI+2O9wtcwXoMo1tH8bqW7lT1R+9o+bP2F8M+MjuFy57XPX4fFM/gcxzK3fdDPJgBgHvylWnfWlgOsqZSDBneAVSd4Y2oCmmfVIW0s67is5Is8wvFldy6a7i/ledu9oMPTKmDb2dYh5/39ITUP/9+dRgjYtOxbWvbpTvOWpwOrp4fdprI8uvhi7Gzdhnre8nbnDL7mI5/v/nHV+64Dtmr5p1T+q9jGfN6fqkcwLQ0P2PrbUf4mpU151rcV15ZlUTr6gkZrivU9QqQ27lJw8F7P59vM9zuv9pyU9zvjFmbb5yMqdTwqqG1cUh9PkT+bA69dbHud1Lbvx/p5BNKjrvv8DFe9TPW79Qsr5n3HaxDFOqkZffaoqZ8/nHFLdMOGDW+u54t8HmcdQ5WuiuuYP//el9Kz9a1NzW/SNs+uqhKwAcCx4C/VurM2zZ+nL9zp0lnkAKIEbKd7moO6g+4QPO8v91y39zZm/rLvddK57sCAzfO5zo62Djlv67qWct8+nFU+1oxAXFpm8j5863BWxxKl5oWDW0OxO+JZnb7KbnKQEcvzscSOcUaaq7MeNWBT/gnlD5Z1YhtVdrPKDmv6o7pcZbvjLc7yGfC2U/XAeMrP8vk6K10TPysLEdusbW9Nzfn/sdJ1nfwsZVynnm9T1/H6SlPV4t718XHU53gxdJrbgDO2qX2fobQpNYFj71zm8lcbsJ3geU3H1fZry3XII8mTo3y2Xw0FbB92UKv9nFKukfKfyW1w2/oj5m379jH7esZyAMA8uWNM1Rue3SZYe17pnKqOb4uV58YcePV+u1f+B1W+96Wemt/Yy+243jp5mx4N255HsHaX39o99bwDiBIEKp2Z1zvFZVrvapX929vNb4b+LO/rVqWHnS+0zgdSeEMtd/xHSns0vTLPT9b1TOs/WndAmr9G9V5JR0eZesooZF22WNzOVAWibmuV36Fz0Ml5n6upnPfzfH72zZ25X0S4TPNnTExMvE3539XH5PXiCGL3aCDma9cLknzMSi+WOg5GqnoL5hFPbX+v89ru5cof9uejLB8WsPl4U8s1jHXyyzMz+DhicLVAvWca4+hakZqA7Zlqvh+M5fPga3d9f4VQR/kr/dnO+QuV79b12oKm+co/o3c6n/+u2vZYJ1VvSLft29cghZ8ZAMA85Q4vpr/Vt1dSfgg+pymlPakZtfCtoUerenco3Ve+3DV9SPMvp+ah7x+mJujZ4k6ybK/OO+Xt+BbcYW37F5o+mDfvUYWLNf9HpT+n/OxctxmR6XeC6vhOq7bXGyXrNreESpn3uVnprBRG3PK6fqGhXzenfar31VKvUNk6LXsuli9Uqs537vQO5Xmf+8+WZTng+Fxq2nyb8h/X9Jfd5uH6uk59vnvHq/wLKQevheuWvJY9pnSnr2+qAiZvq663GFIzonan0gNK/6mXaX+XquyRUFYHY62jpqHOM6klqCvnJpbPVx7p2jM24CUUn0tfrzKfqmAsv2U93QmBUV0n/2Ljz4B/7p6M9drOw0Jom/tS85LL3ng7V+3doDZ8pMy37VvrbYvrAQD+f3lUw4FZayc5F3eEg0ZDRqH93tFdojcOl1pqRvBmjEK2BWK5Xv+Fg6UI2ArtZ0eqXjhQflN+8cS33PvXtw7GBl3Dus4gix2wzUX7+bqn5Vk9c5BV3xL1KGAKz5PFOoO4XlvQtBS0r+/52nSqN0DjvlNzG5i/wwYAmCk1b86NTJ38u7XO7bF8VPl26IWx/HjSaf4MxallPgZiqRkRPZKaP63i5b7V7NG/f6Tq7eDFoO09kvfldGZqXiwp8/G5vHr0rPUaDgvY3P7UHMd+H1dcvpi0/bOrY6mfDYwvFMz6PMU6bVTnqtT86Y3d3eq/T1sKqfmzOuVY+o8itARs9zO6BgCYRR3VN8fCW3NLSR3Sd8aO4f6WSsrPAloM2JarYcGYjVLntTZiMDa0znJQB2xq86bJ4/z/2QUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP9F0P5FbWYWCGyAAAAAElFTkSuQmCC>

[image14]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEMAAAAZCAYAAABq35PiAAACrElEQVR4Xu1XO2gUURSdYAS/IMi67vftusWiiAqrhSAWEtAUgmgKRUGwsdNGCNiKaIiNFoIiioIIsmCVRpvgFoqVWIitstgE7GIjRM9h7oY7d2YHZ52EgO/AYWbuve/Ou+f9ZoLAw8PDIwOcc5PgQ8tGo7ENPGDt4rvbbDb34Xrb+hTv1+v1qWq1utG+c5Ux1mq1dqA/h3nlsw1YRqFQ2FKpVKoIvg7+Br+Cx+Bah2I34L4EXgJ/gYuwnYUQRfqYvFarHZR21yS2BNteCHFFci1IvlUH+rgT736D62vwIu5fgO9tXAzo/Ekpap4CGV+HQkhxJe1jLNuxvbYT7XZ7K3w98U9b/wDlcnkTYmaZo9PprLf+UYBcE8i5BJ429iMcUG2LYSXEEN+85H1k/RrFYnEzclxF3Ede+WxjsgB5bsp7J7VdankepC2XlRBDll8fXMJonLD+JHBmcOQoin1XBoyjbZd9Zt+1A0t8f1KNESgxFnD/xEU3w1csyGUQQ0b6luS8M8L05571Fm27yLMnSBtJAzUjY2Kw/0l1RKDE+IL7C+CU4rQLN9BYkoEY4A/EfSNx/x38CfYwEkeDDIVYoH0bojxFrndONnYbY5GnGLEpxIRMnJRk2MzIG1hy2yHKDPgJ7zsTpAj8X4kBnoNp3MYMwGMffZpLEgPPu2Dv8aTT9gjWqhhcJsj/DAV+cH+5TAjE3kvql9TSDVLE/GcxnDnPc8BgA53j126QsiySwNPLhZv+eW1HLRPwXda2GFiMFBWbQviiPOTCDbHP41L71MwY+lGVBTkdrXrfeKlOsjE837A1LINFiAiWJTVbLBch0HEXzpSIb1RR8v7oIpBrN/gZfFwPT0Ue9X0bt6bAUcRseACeGuF7JBXMx/8nisFjPu/8Hh4eHh4eHkPxByCFIUIw2UAsAAAAAElFTkSuQmCC>

[image15]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAAZCAYAAAD6zOotAAAFkUlEQVR4Xu2YW4iVVRTHz2EmmOim1TTN7ewzFxqMLsp0oR4yREyZIlIDSYlIQgqfCpIkQh8kpAvoEIVjVA9hlmCRUg/zIBo1aA8RhYMVjVGJQfnkQIWdfv9v7z3uszvnzDlnzpAO3x/+fN+39tpr7b3Wvn6ZTIoUKVKkSJHigkBXV9elxphx+A/8Df6Sz+f3dnZ2dvX09JhcLvcpsva4XorZBTmYR9zvVh74bIrLqwJGFmLke7h2cHDwEi8nsbcg+wyedLzoE6z+9fb2XhXLL0Qwqd4i5l/C9XAYfkuuFsd6ZdHa2no5lQ7BAsbWxeUelG2aKwmmDxsJ0juxvF4Qmxuxt0PPuGwmoJ0L4OZQho9eZKfwtyWUlwWKy41dkidYojvjcg8MD6Lz1cWeYPp7vZsFDUuwgM0eOAKXZOpdRiNgay18OpK1GzvRjgwMDFwRlpUEirthAR6k0y1xuQfr/zUk+Q099d3R0XEtdV6Bx5H/ZGzyV1GUVbnbN15SGcv8MniPGqVvt5cvcnv+U67uiILv/Rm7JI1KX7OD9yFXb8z5SYJIWV7tQjbubC918r3IfuD5NX5uRtTM+4PIvjG2vz/CXXCF9yloFiI74Pp0Cu5xe19VwMd2+aT+o+pfXF4L8L0NOw+EMuLYpn6ZalbTcHmudURTZ4I6z2VcoOlMP7Lj8GW3hze5WV+An8PHJdPeR73DaiTlb/N+H/Ksa/THPiiyR/kLxq4u5+Srra3tMj0lo+x1+RH5XuJ8aJtJAsL7Q87mWbVDPjQ45Q/ZJPwAtisGrktKzmJkp+F66Tvbu5Cf8DrVQO2UDdXj+byfFLVCOYkTHOTM96s86k2wqzcWH1SMXVKUkJWBrAD38NrsZTm7nysZmwK9d000Kt0AOauyjFsZXNDflx/avDzQ9TanAqI+qX4YCG8z7m9fX991xs7uY+jM9/Lu7u7bkU2GujWgibpD8Av4JuyJFSphxgkGzSjuU2BMEMQyyLo1P4vhpXGAhCAh+zIuobIdJtLplUtGyQTHvowdSGrz7kC3nM2qEqw+GTtoDvO+OuATyM+EunUg624jB+EnTIwbYoVSaESCZWSDC1bRyI2h5Mqh9gA5jQMk+OCpAX7pc0FvaIJVz7V5yk8Fm9UmOLFZIsEJQ906UJRg3m+NFUoB3Z1hfwS+5yM/Bn+u6mzA0tSN8nfwT3hXXO6Rs8dzHYRa5DQOkNPxCR7VPiSZC/psJXhqpahgs2KCjd0rW3iuUP3Y1wyRLNHYPJqz99lal+gNcewUHxenihOyCCivgufgaFzmkMXZVrhGH2qoCWaPB7KVLkhbAlmjE6y2bFd9Yw9DXrfIpkuaZkzFBOupfmhlMvaQ+J/AoZMPv6dDeMhSW+s9ZLH/34SdbaHM2Lvx73BnKJ8OWSo8owBxer06LqORj1E2HP7h4vsMHPLfOnDxPSqGhy/ZjBOMbLOTTyXY2ENW0bITJOMECTCS8bzD+S7yg86a0Cbfd6ounNRByevpro9sAu5Xf9DbgTg5exg70P/GxrNeBpry1f5UyCR+G3ZNytir3dFwgGB3HW38Ay4KFauB9gndVXUl+Uid5LmV7zHeX4wbi+x+yn41dsPXCVFXkhE/QMz5paTgeFLBNzboXiaq/iOhLO9ml0+wsffnD3N2mdMVZ7i/v//KsD1KNuXvGZs8tec1uD+2mbGDeSP8Cx4g+bcFZnSAVL90VRp3do5Q98lApyTMLPzoEIydNPpHoQGsSXiaNj6cOT8Aa4NGC4lehpHVGL03XoYjJHdLnLbnK/wkqRfBDPbL6bzp/LhTZrLMS19Lb7jyeMiOymK5Q9KvcnVjYGuhBl+uwb8qHbSPL1A+lBd/tpkTiBOcYg6BxL6as78eQya/IVOkSJEiRYoUKVKk+N/wLy2zGF9v+3moAAAAAElFTkSuQmCC>

[image16]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADYAAAAZCAYAAAB6v90+AAADV0lEQVR4Xu2WXYiMURjH32lXEfI5jd2dna+GaVHappSNfBQ3WsnSKly5QMmFzXJJkbR3S1FILrTZspG2tEniRq2wF0q2LSslhBu29mr9/vued+fsMTPe/cjV/OvfOed/nvOc8zzn4309r4IKKiiCSCqVak0mk+8SicQhtV0DIZ/Pz8HmMrZb3L5ZQzqdjnnOAszENbYmsJDF6E11dXVxmlVuf319/S7632KXorxJ8YAAV3uWf/Q07EG/pnms4bMLJhmGv+ALFnKbchCOUD9m28VisfnoL+FhZdsEsDnopz4XrRfeoRlh4RtVh+fhK/haJXZ9lG9IaNJyHx44zmsBru4Cm+dMso6yRjvi9gv0NcDvtob/DNpnxpw1NjVwWMlRW7uKzS0lJBhD31F4zitxRENhCoE91aJc3Qb9B+CYo40HosTkcrmFZkcfB4Fpx6hfsuwbYU8mk1lU8DINyLHOsau7UGAmu3kWshumPCej2FxwA9PdRBsywY0nBh8HqQ/Kh+aG26UrGPRuxqy3fUwLOG0OslcO2Lxn0gHsTyT9ndFduBePx5daNrp7kwKLRqMLlBT4W0kxchXt47Q/pvw7qgTppTyD3lYYPQOEDYwJe+2LTEAr0b4qw8GrNYXA/gIv5SZsuvA7T212bxXtJ3CIcRcDvRgiGDVhtNemzjd85uoi9jvtS23DWvAo3CBtuoHpiDO2j8Vngzb2A2itnv9yttM+5QybwIwCY7Jl8hE4sxY8BvdIo+x0A8PPErR++Ml81yYh+AjDlkBjPUeS1p2sra1dTr27MCoEEiGOornUY9jtD7RigZkFlXoV+xWk3Wf6WxSY/RE2Oz8RGKimfj3oD4UwgZmsf9N3zNG0Ez+5H2ulqVS7MLLwbYOdth5AR9DdySKB6bRdsW3+iTCBCdi1e9ZRNJd9FP0qzWojK7M3zLEdR8J/2n/AxkALoAdBflydMaftwJRE1njXtSuLsIExSRe2j5L+U6+7NAI73NcKXyvQe3VsKdvgF8bt84r8RdB3spiO/Rr6PsCtaqf8H+YO164swgYGInqCE/7D0qwPr2sQgEU0yA6bHaVeVfpySf9/sSjo2wYH4EN83c9ms1HXpizMIpTR/42qEH/tkVKJqaCCCiqooBj+AAUa/pUYRl0mAAAAAElFTkSuQmCC>

[image17]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAZCAYAAAB3oa15AAAC70lEQVR4Xu1WO2hUURB9S2LhB/yuS/Z33+6KjYLFqhBRsVDBIjaxEFJaCJYGESxEEAl2IZYGITarURAR8VvE0g9+QAkIgoG1FgSFFBrPYeeus+N9a2IKI7wDw7v3zNx5M/fOnfeiKEWK/xPOuWHIB8jzUqm0w+o9oB+M4/ic5buiVquVLKfQUygUinC8C47XWKUgAx8bYdPPJ+fWALqparW6ulKpYOhelsvls/C73uuLxeJy8Ceoo41eG0S9Xl8GJ1uw4DJ3xuoJON0E3WvIVQR/HPIMcpFrlc066O+Bf4jnMfi8j2eDwXqbbDa7CtwZP8d4mAlgzW2MX0FeYP4EzzeQQW83L8DJBBbNWB7HfBj8LBzv1jy4C5BpjqGrY/wVMmRshiCf4WOrzPtge9rrMR7Qczm9m/PaeYukBMCNMTgGqXm+GPwPjnkqGM8xIGMzQJ56ma91nSdwCnJIphmeqlvoznuEEsjlcivBPe6SwBzHeI53SwAy5jknd0B2uyF3hbYHML+ky3JBCCUgNTsFafICa51OQNZ+s11FncCE4kbAfQL3HvZ7yElzuPVXpePxhwRmIH1aF0ggdEq/JRBAL/SjTkqHJ+BarXYa8sgaJ+JfJSBNol06DB721znHiexkW7VrgggloO7AFzjbpnWhO+B+XUhv4+/AuOY9bOnk8/kNmL+DnBSTjH1vIkIJEBJcaHfbXYgvZKBJlziWLmTQUToE3yHvavuxPhORlAD4o+C/w9F+zbtWe23KuB8yawPlnDz1mids6RCLSaAHhtd8QBrS7t5Czkfya8BPf9z6Go9yLp//O5BJH5Bcxknyto5t6XjArgD+o94I29k64DN2rTptC8tD28HJdvBN8CNyInchN/Rvgvzb8BfgCuyO8MkkbfuNAqWjwI8ZdbwztIv1OxYFXmgEeZDBwenmSE5DQzrHXtpwc0D1WBvEtE9OrtfqCAaMBBpY/wDy1OqXAhh4MHgNdKQVUWADUqRIkWJp4CemOwKy3y+/bgAAAABJRU5ErkJggg==>

[image18]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAWCAYAAAArdgcFAAABRElEQVR4Xu2TvUrEUBCFI9usoLCiUcz/D5hKLATfYQvZBbcTLLbxAcTCTrBSsBIsbMRSbK2stNVaLAV7fQNdv5FkuZlViahdDhxu5twzZy43iWXVqGEiDMP5KIr2gyDoCanXqc/hrvYOgXEZ45HWNfJwCTvj+UD6kMe0r4SfhAu1/i3+NZyGNgNOta6RX0uH9RL/k/T4vp9qXwmYVuUeta6Rn/zYdd1pygY9O9QvcRyvaO8QVcPxtGzbnihqQucIf0C/lc0mxTY8MYl+xfqo9ZyH4Rf3LIPYu4ZvH4JMF7NJTr7BeqF1YZqms7Q1pNfzvEU4/kn4oNBGUOVaHMeZIeQe32ah/Vl4lmWT+G7k9IVGPUXwHXw2vSVUCRcQsmUZfyT1GnyFe4atjKrhgiRJFvD38Hd5H77eHwGf1BLT+1qv8Wu8A0cSVKdvfYD/AAAAAElFTkSuQmCC>

[image19]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHUAAAAaCAYAAACJphMzAAAEgklEQVR4Xu2ZW4hVVRjHz2FGSFK8NU3O5ax9ZqJpiqgYSxwKScdg0AlRQcUeeiuGnooY8aEo8SER81IQkyImKFlgkYLiwIS+BEFEIIpPKuI8DCUJiWPMTL9v9tozy899zmzP1ZH1h4991ndZ69vrv677pFIeZUdzc/NmrfOYAchkMmuy2WyPkjdbWlpWIl2NjY0v6hiPhxyQ+qkx5rNI3DIzdXsQBM/qGI8ZiqamphcgdljrPTw8PACb+CLW/M9ZJvoTyE7kDcJqdD0VRA05rGDfOsPzb+QG+f+JLO/o6JhFeRe/1+qgciCmf/pp+yXXR8rKp9u1lwO1NHKUht/hd1oUlNuRv5ALDQ0NT7jO6HbQmX2urlKg7XXIXWSAfJ+KsS9DRpBf6urq5mh7PlDfRuIWa30SEHcAGc/XL9i+lgGn9WUByWSR7zl2z3N0WyRJ5AeKtY672LabCow0Ddpcj4wiA26uLui4Bdh/Q/Zp23QgZj/xHVqfBEKm9BcD47C2CTgsPc1q2KT1ZQOJbCKhXldHkodsku+6+lQ4q7/h/lXROxftGXK5TNsjXA9e1/YIMjvxGcTnLW2bDsWQasIVZBw5RZ6PuTaZnTJLXV3ZUV9f/7heFuxo/zfmJdMyG1KV3U/TdNQe22nHUmrlcCHvIuTIINC2aSCD9WDM+yYCcV3EjyHn29ra5ro2dOsrTmochFAh1hL4IEgT10nchqSC/2ohQ1cUwYTbw3UhtZAZmAQyw8nlx0JJlZWL/G4hV42zL8uSS/lnBmXguFcH0oHIAa1PgHKQ2m3zGcK/RdtLgWJJFSItobecrUlm/1fU+fY9zlWCJCOduEUbqgHy+MDmc9/SpmHtObcGOckzadbqgSUdT/2/8+zTNvkipOvRkHYlP2SMmC7RyapC+dtoa6Pdveb+689O9EtTKmfb5sRNpCSgwkYTXmfata0akMOaJTXvNUVOxPgck/y1LUK5SJXDEfGnbJ7rWltbn+R5lvjnIx8hF7/vzNTglLNCYMk97p7oUV+WOqJy0SCR16brwDwo+fJr8/nP6YxY0BEb8f04VcAIL3b5FdD+YSGV51aeu3m+F+cj4ursx5Lj6PekbO4Q2uz6FI1MeOd64HueRclJtTPwVxN/Gp8AtnbpLPkypm1JUApSbb+Nm/BQdyJuUsSRKjDhlWhydbSzVJbktLyT1EXc/EBdlxKBpWY2yZ2WRrStmuDw8So53eSlzulLPPoVyMkCrjGTKAWpZuqDzU3kZW0X5CKV/fcVYm7Tfg92WZInTtFIL/KPCffrI8iVRO/JTKCuzDWbkJZh7M/omGrAvvhFZJT3/onnNmQ3uX+Rb6YnQSlIzYR3Vfni9aG2RchFqrRrwpWoR8r8/sPYq5H4oz8kMxZdt/6m8CigBnJbA3vY4fcS7VAISkEqq9xC4lfJaqdtEXKRKmTJgJCBYcua1JzflD2qjDhSIa8TuR7NUqvzpM4EQNKXyJCVgya8ysgBcBDSnov8gvBvujvoPmH/fN/6X0I+Cgo5KHl4eHh4eHgUjP8Bxx132nzhFzQAAAAASUVORK5CYII=>

[image20]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAZCAYAAAAIcL+IAAAA80lEQVR4XmNgGGLA2NiYVUZGRlVUVJQHXQ4O5OXlnYD4PhBPAuILIFpcXJwbXRFI8om0tLQMklgrSAyIFcECcnJygkDOaSC+q6ioKA5TCBQvB4r9B+IgmIASkPMciA8guw3ILwIpBGmAKTQGCnxFVwgU9wUpVFBQWEgjhUCOJhC/RVcI5EeDFAJxFVhASkpKBMi5CsQPgVgSphDJ19EwMUYgZwoQPweFAExQHhK2IJs0YWIwd34C0jEgPjDghYFuOwXkTwdyWeAKgYARKBgHVPwSiIuBeCuQvxMY70LIiuBASUmJHxg7bkBaDchlRJcfBTgBALJjSNox3g4pAAAAAElFTkSuQmCC>