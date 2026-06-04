"""
llm/ollama.py
Ollama local inference client.
One call per bot per turn. format=json enforces structured output at inference level.
"""

import json
import requests


class OllamaClient:

    def __init__(self, config: dict, verbose: bool = False, trace_path: str = None):
        self.model       = config["model"]
        self.base_url    = config["base_url"].rstrip("/")
        self.temperature = config.get("temperature", 0.7)
        self.timeout     = config.get("timeout_seconds", 30)
        self.verbose     = verbose
        self.trace_path  = trace_path

    def call(self, system_prompt: str, turn_request: dict,
             handshake: dict = None) -> str | None:
        """
        Call Ollama with system prompt and turn request.
        Returns raw JSON string or None on failure.
        """
        # Append JSON formatting instructions if this is a bot prompt
        if "map_name" not in system_prompt and "winner" not in system_prompt:
            system_prompt += (
                "\n\nResponse Format Rules:\n"
                "You MUST return a JSON object matching this schema:\n"
                "{\n"
                "  \"thought\": \"your step-by-step reasoning for this turn\",\n"
                "  \"action\": \"one of: next, move, eat, capture, attack, peek, build\",\n"
                "  \"direction\": \"required for move, attack, peek, build (one of: east, south_east, south_west, west, north_west, north_east)\",\n"
                "  \"target_structure\": \"required for build (one of: barricade, collector)\",\n"
                "  \"save_memory\": \"your compressed memory string for next turn (max 400 characters)\"\n"
                "}\n"
                "Return ONLY raw JSON. No markdown code blocks, no backticks, and no extra conversational text."
            )

        messages = [{
            "role": "system",
            "content": system_prompt
        }]

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
            }
        }

        if self.verbose:
            print("\n" + "=" * 80)
            print(f">>> LLM REQUEST (Model: {self.model})")
            print(json.dumps(payload, indent=2))
            print("=" * 80)

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = data["message"]["content"]

            if self.verbose:
                print("\n" + "=" * 80)
                print("<<< LLM RESPONSE")
                print(content)
                print("=" * 80)

            self._log_trace(messages, content)
            return content

        except requests.exceptions.Timeout:
            print(f"  [LLM] Timeout after {self.timeout}s")
            self._log_trace(messages, None, f"Timeout after {self.timeout}s")
            return None

        except requests.exceptions.ConnectionError:
            print(f"  [LLM] Cannot connect to Ollama at {self.base_url}")
            self._log_trace(messages, None, f"Cannot connect to Ollama at {self.base_url}")
            return None

        except Exception as e:
            print(f"  [LLM] Error: {e}")
            self._log_trace(messages, None, str(e))
            return None

    def _log_trace(self, messages: list, response_content: str | None, error_message: str | None = None):
        if not self.trace_path:
            return
        
        import yaml
        import os
        
        record = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": messages,
            "response": {
                "content": response_content,
                "success": response_content is not None,
                "error": error_message
            }
        }
        
        traces = []
        if os.path.exists(self.trace_path):
            try:
                with open(self.trace_path, "r", encoding="utf-8") as f:
                    traces = yaml.safe_load(f) or []
            except Exception:
                traces = []
                
        traces.append(record)
        
        try:
            with open(self.trace_path, "w", encoding="utf-8") as f:
                f.write("# Prompt Wars LLM Call Trace\n\n")
                yaml.safe_dump(traces, f, sort_keys=False, allow_unicode=True)
        except Exception as e:
            print(f"  [Trace] Failed to write trace to {self.trace_path}: {e}")
