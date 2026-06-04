"""
llm/ollama.py
Ollama local inference client.
One call per bot per turn. format=json enforces structured output at inference level.
"""

import json
import requests


class OllamaClient:

    def __init__(self, config: dict):
        self.model       = config["model"]
        self.base_url    = config["base_url"].rstrip("/")
        self.temperature = config.get("temperature", 0.7)
        self.timeout     = config.get("timeout_seconds", 30)

    def call(self, system_prompt: str, turn_request: dict,
             handshake: dict = None) -> str | None:
        """
        Call Ollama with system prompt and turn request.
        Returns raw JSON string or None on failure.
        """
        messages = []

        # Inject handshake as first user/assistant pair on Turn 1
        if handshake:
            messages.append({
                "role": "user",
                "content": f"GAME RULES AND SCHEMA:\n{json.dumps(handshake, indent=2)}"
            })
            messages.append({
                "role": "assistant",
                "content": '{"thought": "Understood. I am ready to play.", "action": "next", "save_memory": ""}'
            })

        messages.append({
            "role": "user",
            "content": json.dumps(turn_request),
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "format": "json",   # Ollama native JSON mode
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
            "system": system_prompt,
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

        except requests.exceptions.Timeout:
            print(f"  [LLM] Timeout after {self.timeout}s")
            return None

        except requests.exceptions.ConnectionError:
            print(f"  [LLM] Cannot connect to Ollama at {self.base_url}")
            return None

        except Exception as e:
            print(f"  [LLM] Error: {e}")
            return None
