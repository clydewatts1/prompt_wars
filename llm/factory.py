"""
llm/factory.py
Factory to instantiate LLM clients based on configuration.
"""

from llm.ollama import OllamaClient
from llm.gemini import GeminiClient


def get_llm_client(config: dict, verbose: bool = False, trace_path: str = None):
    """
    Returns an LLM client instance (OllamaClient or GeminiClient) based on config['provider'].
    """
    provider = config.get("provider", "ollama").lower()
    if provider == "gemini":
        return GeminiClient(config, verbose=verbose, trace_path=trace_path)
    else:
        return OllamaClient(config, verbose=verbose, trace_path=trace_path)
