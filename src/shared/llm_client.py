import json
import os
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any
from .utils import load_secrets


class LLMClient(ABC):
    @abstractmethod
    def query(self, prompt: str, system_prompt: str = "") -> str:
        pass

    @staticmethod
    def create(provider: str, **config) -> 'LLMClient':
        if provider == "anthropic":
            return AnthropicClient(**config)
        elif provider == "ollama":
            return OllamaClient(**config)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")


class AnthropicClient(LLMClient):
    def __init__(self, model: str, temperature: float = 0.7, **kwargs):
        secrets = {}
        try:
            secrets = load_secrets()
        except Exception:
            secrets = {}
        api_key = secrets.get("anthropic_api_key")
        try:
            import anthropic  # lazy import to avoid hard dependency when unused
        except Exception as e:
            raise Exception("Anthropic SDK not installed. Run 'pip install anthropic'.") from e
        if not api_key:
            raise Exception("Missing Anthropic API key in config/secrets.json (anthropic_api_key)")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature

    def query(self, prompt: str, system_prompt: str = "") -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=self.temperature,
                system=system_prompt if system_prompt else "You are a helpful assistant.",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")


class OllamaClient(LLMClient):
    def __init__(self, model: str, endpoint: str = "http://localhost:11434", 
                 temperature: float = 0.3, **kwargs):
        self.model = os.getenv("OLLAMA_MODEL", model)
        self.endpoint = os.getenv("OLLAMA_ENDPOINT", endpoint)
        self.temperature = temperature

    def query(self, prompt: str, system_prompt: str = "") -> str:
        try:
            url = f"{self.endpoint}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt if system_prompt else "",
                "stream": False,
                "options": {
                    "temperature": self.temperature
                }
            }
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result["response"]
            
        except Exception as e:
            raise Exception(f"Ollama API error: {str(e)}")
