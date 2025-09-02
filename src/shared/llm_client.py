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
    def create(provider: str, json_mode: bool = False, **config) -> 'LLMClient':
        if provider == "anthropic":
            return AnthropicClient(json_mode=json_mode, **config)
        elif provider == "ollama":
            return OllamaClient(json_mode=json_mode, **config)
        elif provider == "gemini":
            return GeminiClient(json_mode=json_mode, **config)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")


class AnthropicClient(LLMClient):
    def __init__(self, model: str, temperature: float = 0.7, json_mode: bool = False, **kwargs):
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
        self.json_mode = json_mode

    def query(self, prompt: str, system_prompt: str = "") -> str:
        try:
            # Anthropic JSON mode is often managed via system prompt or specific model features
            # not covered by a simple flag, so we just note it here.
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
                 temperature: float = 0.3, json_mode: bool = False, **kwargs):
        self.model = os.getenv("OLLAMA_MODEL", model)
        self.endpoint = os.getenv("OLLAMA_ENDPOINT", endpoint)
        self.temperature = temperature
        self.json_mode = json_mode

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
            if self.json_mode:
                payload["format"] = "json"
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result["response"]
            
        except Exception as e:
            raise Exception(f"Ollama API error: {str(e)}")


class GeminiClient(LLMClient):
    def __init__(self, model: str, temperature: float = 0.8, json_mode: bool = False, **kwargs):
        secrets = {}
        try:
            secrets = load_secrets()
        except Exception:
            pass  # secrets are optional
        
        api_key = secrets.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
        
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise Exception("Gemini SDK not installed. Run 'pip install google-generativeai'.") from e
            
        if not api_key:
            raise Exception("Missing Gemini API key. Set GEMINI_API_KEY environment variable or add 'gemini_api_key' to config/secrets.json")
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.temperature = temperature
        self.json_mode = json_mode

    def query(self, prompt: str, system_prompt: str = "") -> str:
        try:
            # Combine system prompt and user prompt for Gemini
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            
            generation_config = {"temperature": self.temperature}
            if self.json_mode:
                generation_config["response_mime_type"] = "application/json"

            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
