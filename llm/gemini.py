"""
llm/gemini.py
Google Gemini API client using requests.
One call per bot per turn. responseMimeType="application/json" enforces structured output.
"""

import json
import os
import time
import requests


class GeminiClient:

    def __init__(self, config: dict, verbose: bool = False, trace_path: str = None):
        self.config        = config
        self.model         = config["model"]
        self.api_key       = config.get("api_key") or os.environ.get("GEMINI_API_KEY")
        self.temperature   = config.get("temperature", 0.7)
        self.timeout       = config.get("timeout_seconds", 30)
        self.delay_seconds = config.get("request_delay_seconds", 6)
        self.verbose       = verbose
        self.trace_path    = trace_path

    def call(self, system_prompt: str, turn_request: dict,
              handshake: dict = None) -> str | None:
        """
        Call Gemini with system prompt and turn request.
        Returns raw JSON string or None on failure.
        """
        # Sleep to throttle requests and respect rate limits
        if self.delay_seconds > 0:
            if self.verbose:
                print(f"  [Gemini] Sleeping for {self.delay_seconds}s to prevent rate limits...")
            time.sleep(self.delay_seconds)

        # Append JSON formatting instructions if this is a bot prompt
        if "map_name" not in system_prompt and "winner" not in system_prompt:
            system_prompt += (
                "\n\nResponse Format Rules:\n"
                "You MUST return a JSON object matching this schema:\n"
                "{\n"
                "  \"thought\": \"your step-by-step reasoning for this turn\",\n"
                "  \"action\": \"one of: next, move, eat, capture, attack, peek, build, push, kick\",\n"
                "  \"direction\": \"required for move, attack, peek, build, push, kick (one of: east, south_east, south_west, west, north_west, north_east)\",\n"
                "  \"target_structure\": \"required for build (one of: barricade, collector)\",\n"
                "  \"energy\": \"required for push (integer >= 1 representing energy to push the rock)\",\n"
                "  \"save_memory\": \"your compressed memory string for next turn (max 400 characters)\"\n"
                "}\n"
                "Return ONLY raw JSON. No markdown code blocks, no backticks, and no extra conversational text."
            )

        contents = []

        # Inject handshake as first user/model pair on Turn 1
        if handshake:
            contents.append({
                "role": "user",
                "parts": [{"text": f"GAME RULES AND SCHEMA:\n{json.dumps(handshake, indent=2)}"}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": '{"thought": "Understood. I am ready to play.", "action": "next", "save_memory": ""}'}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": json.dumps(turn_request)}]
        })

        generation_config = {
            "temperature": self.temperature
        }
        
        # Enforce JSON mode unless disabled in config, or if model is gemini-3.1-flash-lite (known to hang/timeout with JSON mode)
        use_json_mode = self.config.get("json_mode", True)
        if "gemini-3.1-flash-lite" in self.model.lower():
            use_json_mode = self.config.get("json_mode", False)

        if use_json_mode:
            generation_config["responseMimeType"] = "application/json"

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": generation_config
        }

        # Convert to standard role/content format for logging compatibility
        log_messages = [{"role": "system", "content": system_prompt}]
        for item in contents:
            log_messages.append({
                "role": "assistant" if item["role"] == "model" else "user",
                "content": item["parts"][0]["text"]
            })

        if self.verbose:
            print("\n" + "=" * 80)
            print(f">>> GEMINI LLM REQUEST (Model: {self.model})")
            print(json.dumps(payload, indent=2))
            print("=" * 80)

        if not self.api_key:
            err = "GEMINI_API_KEY is not defined. Set it in your environment or .env file."
            print(f"  [Gemini] Error: {err}")
            self._log_trace(log_messages, None, err)
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        max_retries = 5
        retry_delay = 12  # Fallback sleep time if rate-limited

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                
                # Check for rate-limiting
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        cooldown_seconds = retry_delay
                        try:
                            err_msg = response.json().get("error", {}).get("message", "")
                            import re
                            match = re.search(r"Please retry in (\d+\.?\d*)s", err_msg)
                            if match:
                                cooldown_seconds = float(match.group(1)) + 1.5
                                print(f"  [Gemini] Rate limited (429). Google requested retry in {match.group(1)}s. Sleeping {cooldown_seconds:.2f}s... (Attempt {attempt + 1}/{max_retries})")
                            else:
                                print(f"  [Gemini] Rate limited (429). Sleeping {cooldown_seconds}s (exponential backoff)... (Attempt {attempt + 1}/{max_retries})")
                        except Exception:
                            print(f"  [Gemini] Rate limited (429). Sleeping {cooldown_seconds}s (exponential backoff)... (Attempt {attempt + 1}/{max_retries})")
                            
                        time.sleep(cooldown_seconds)
                        retry_delay *= 2  # Exponential backoff fallback
                        continue
                
                response.raise_for_status()
                data = response.json()
                
                # Extract content from candidate
                content = data["candidates"][0]["content"]["parts"][0]["text"]

                if self.verbose:
                    print("\n" + "=" * 80)
                    print("<<< GEMINI LLM RESPONSE")
                    print(content)
                    print("=" * 80)

                self._log_trace(log_messages, content)
                return content

            except requests.exceptions.Timeout:
                print(f"  [Gemini] Timeout after {self.timeout}s")
                self._log_trace(log_messages, None, f"Timeout after {self.timeout}s")
                return None

            except requests.exceptions.ConnectionError:
                print(f"  [Gemini] Connection error reaching Gemini API")
                self._log_trace(log_messages, None, "Connection error reaching Gemini API")
                return None

            except Exception as e:
                # If we have retry attempts remaining and it's a transient server error, we can retry
                if attempt < max_retries - 1:
                    # Treat HTTP 5xx errors or connection drops as retryable
                    is_server_error = False
                    try:
                        is_server_error = (response.status_code >= 500)
                    except Exception:
                        pass
                    
                    if is_server_error:
                        print(f"  [Gemini] Server error ({response.status_code}). Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                
                # Otherwise fail
                try:
                    err_detail = response.json().get("error", {}).get("message", str(e))
                except Exception:
                    err_detail = str(e)
                print(f"  [Gemini] Error: {err_detail}")
                self._log_trace(log_messages, None, err_detail)
                return None

    def _log_trace(self, messages: list, response_content: str | None, error_message: str | None = None):
        if not self.trace_path:
            return
        
        import yaml
        
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
