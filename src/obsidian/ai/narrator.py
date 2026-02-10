"""AI Narrator for OBSIDIAN MM diagnostics.

Generates natural-language diagnostic explanations using Claude, GPT, or Ollama.
Falls back to template explanation if no API key is configured or API fails.

Usage:
    narrator = Narrator(provider="anthropic", api_key="sk-...", language="en")
    ai_text = await narrator.narrate(diagnostic_dict)
"""

import hashlib
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# Default models per provider (cheap/fast)
_DEFAULT_MODELS = {
    "openai": "gpt-5.2",
    "anthropic": "claude-opus-4-5-20251101",
    "ollama": "llama3.3:70b",
}

# System prompts by language
_SYSTEM_PROMPTS = {
    "en": (
        "You are OBSIDIAN MM's diagnostic narrator. You explain market microstructure "
        "regime classifications in clear, professional language.\n\n"
        "RULES:\n"
        "1. You are DIAGNOSTIC ONLY. Never predict future prices, suggest trades, or imply direction.\n"
        "2. Explain the assigned regime and what triggered it.\n"
        "3. Highlight the top 2-3 features driving the unusualness score.\n"
        "4. Mention any excluded features and baseline state if relevant.\n"
        "5. Keep it to 2-4 sentences. Be concise, precise, and professional.\n"
        "6. Use present tense. Describe what IS happening, not what WILL happen.\n"
        "7. GEX > 0 means dealers are LONG gamma (stabilizing). GEX < 0 means SHORT gamma "
        "(destabilizing). Never reverse this convention."
    ),
    "hu": (
        "Te az OBSIDIAN MM diagnosztikai narrátora vagy. A piaci mikrostruktúra "
        "rezsim-besorolásait magyarázod világos, professzionális nyelven.\n\n"
        "SZABÁLYOK:\n"
        "1. KIZÁRÓLAG diagnosztikai jellegű vagy. Soha ne jósolj árakat, ne javasolj "
        "kereskedést, és ne sugallj irányt.\n"
        "2. Magyarázd el a kijelölt rezsimet és mi váltotta ki.\n"
        "3. Emeld ki a top 2-3 jellemzőt, amelyek az unusualness score-t hajtják.\n"
        "4. Említsd meg a kizárt jellemzőket és a baseline állapotot, ha releváns.\n"
        "5. 2-4 mondat. Legyél tömör, precíz és professzionális.\n"
        "6. Használj jelen időt. Írd le, mi TÖRTÉNIK, ne azt, mi FOG történni.\n"
        "7. GEX > 0 azt jelenti, hogy a dealerek LONG gamma pozícióban vannak (stabilizáló). "
        "GEX < 0 azt jelenti, hogy SHORT gamma pozícióban vannak (destabilizáló). "
        "Soha ne fordítsd meg ezt a konvenciót."
    ),
}


class Narrator:
    """AI-powered diagnostic narrator.

    Calls Claude, GPT, or Ollama API to generate natural-language explanations
    from structured DiagnosticResult data.

    Args:
        provider: 'openai', 'anthropic', or 'ollama'
        api_key: API key for the provider (None for ollama)
        model: Model ID (defaults to cheap/fast model per provider)
        language: 'en' or 'hu'
        base_url: Ollama base URL (default: http://localhost:11434)
        max_tokens: Maximum response tokens
        timeout: HTTP timeout in seconds
    """

    def __init__(
        self,
        provider: str,
        api_key: str | None = None,
        model: str | None = None,
        language: str = "en",
        base_url: str = "http://localhost:11434",
        max_tokens: int = 256,
        timeout: float = 15.0,
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.model = model or _DEFAULT_MODELS.get(provider, provider)
        self.language = language
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._cache: dict[str, str] = {}

    def _cache_key(self, diagnostic_dict: dict[str, Any]) -> str:
        """Compute deterministic cache key from diagnostic dict."""
        canonical = json.dumps(diagnostic_dict, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _build_user_message(self, diagnostic_dict: dict[str, Any]) -> str:
        """Build the user message from structured diagnostic data."""
        return (
            "Explain this market microstructure diagnostic:\n\n"
            f"```json\n{json.dumps(diagnostic_dict, indent=2, default=str)}\n```"
        )

    async def narrate(self, diagnostic_dict: dict[str, Any]) -> str | None:
        """Generate AI explanation for a diagnostic result.

        Args:
            diagnostic_dict: Output of DiagnosticResult.to_dict()

        Returns:
            AI-generated explanation string, or None if API fails.
        """
        key = self._cache_key(diagnostic_dict)
        if key in self._cache:
            logger.debug("Narrator cache hit for %s", diagnostic_dict.get("ticker"))
            return self._cache[key]

        system_prompt = _SYSTEM_PROMPTS.get(self.language, _SYSTEM_PROMPTS["en"])
        user_message = self._build_user_message(diagnostic_dict)

        try:
            if self.provider == "anthropic":
                result = await self._call_anthropic(system_prompt, user_message)
            elif self.provider == "openai":
                result = await self._call_openai(system_prompt, user_message)
            elif self.provider == "ollama":
                result = await self._call_ollama(system_prompt, user_message)
            else:
                logger.warning("Unknown AI provider: %s", self.provider)
                return None

            if result:
                self._cache[key] = result
                logger.info("Narrator generated explanation for %s", diagnostic_dict.get("ticker"))

            return result

        except Exception as e:
            logger.warning("Narrator API call failed: %s", e)
            return None

    async def _call_anthropic(self, system: str, user: str) -> str | None:
        """Call Anthropic Messages API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )

            if response.status_code != 200:
                logger.warning(
                    "Anthropic API error: %d %s",
                    response.status_code,
                    response.text[:200],
                )
                return None

            data = response.json()
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0]["text"]
            return None

    async def _call_openai(self, system: str, user: str) -> str | None:
        """Call OpenAI Chat Completions API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )

            if response.status_code != 200:
                logger.warning(
                    "OpenAI API error: %d %s",
                    response.status_code,
                    response.text[:200],
                )
                return None

            data = response.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content")
            return None

    async def _call_ollama(self, system: str, user: str) -> str | None:
        """Call Ollama Chat API (local)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )

            if response.status_code != 200:
                logger.warning(
                    "Ollama API error: %d %s",
                    response.status_code,
                    response.text[:200],
                )
                return None

            data = response.json()
            message = data.get("message", {})
            return message.get("content") if message else None
